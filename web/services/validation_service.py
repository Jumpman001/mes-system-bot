"""
Защита от ошибок ввода («защита от дурака»).

Три проверки перед сохранением расхода:

1. ДУБЛЬ. По трубе и стадии расход уже вносили. Раньше повторная отправка
   молча создавала вторую запись и списывала сырьё ДВАЖДЫ — именно так
   работник «исправлял» опечатку и делал только хуже. Теперь это
   блокируется, а человека отправляют подать заявку на исправление.

2. ОТКЛОНЕНИЕ ОТ НОРМЫ. Если введённое значение сильно расходится с
   нормативом на этот типоразмер (таблица pipe_norms) — просим
   подтвердить. Ловит опечатки вида 100 кг вместо 10 кг.

3. НЕХВАТКА НА СКЛАДЕ. Списываем больше, чем есть — тоже просим
   подтвердить (склад мог просто отставать от жизни).

Проверки 2 и 3 не запрещают, а требуют осознанного подтверждения:
экран показывает, что не так, и работник жмёт «Всё верно».
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    ChemistryLog,
    ChemistryStage,
    DryMaterialLog,
    DryMaterialStage,
    LabTest,
    LabTestType,
    MaterialStock,
    Pipe,
    PipeNorm,
)

logger = logging.getLogger(__name__)

# Во сколько раз значение должно разойтись с нормой, чтобы спросить.
# 1.5 = отклонение больше чем в полтора раза в любую сторону.
NORM_TOLERANCE = 1.5

# Какое поле расхода с какой нормой сравнивать.
# Ключ — стадия химии, значение — {поле записи: поле норматива}.
CHEMISTRY_NORM_FIELDS: dict[str, dict[str, str]] = {
    ChemistryStage.LINER.value: {
        "resin_kg": "resin_liner_kg",
        "cobalt_kg": "cobalt_kg",
        "peroxide_kg": "peroxide_kg",
    },
    ChemistryStage.WINDER_FIBERGLASS.value: {
        "resin_kg": "resin_winder_kg",
        "cobalt_kg": "cobalt_kg",
        "peroxide_kg": "peroxide_kg",
    },
    ChemistryStage.WINDER_SAND_1.value: {"resin_kg": "resin_sand_kg"},
    ChemistryStage.WINDER_SAND_2.value: {"resin_kg": "resin_sand_kg"},
}

DRY_NORM_FIELDS: dict[str, dict[str, str]] = {
    DryMaterialStage.LINER.value: {
        "polyester_gauze_m": "polyester_gauze_m",
        "veil_m": "veil_m",
        "stitched_mat_kg": "stitched_mat_kg",
        "ud300_m": "ud300_m",
    },
    DryMaterialStage.WINDER.value: {
        "fiberglass_2400tex_kg": "fiberglass_2400tex_kg",
        "sand_kg": "sand_kg",
        "ud250_m": "ud250_m",
        "sand_gauze_m": "sand_gauze_m",
    },
}

# Понятные названия полей для сообщений работнику
FIELD_LABELS: dict[str, str] = {
    "resin_kg": "Смола",
    "cobalt_kg": "Октоат кобальта",
    "peroxide_kg": "Акперокс",
    "polyester_gauze_m": "Полиэфирная марля",
    "veil_m": "Вуаль",
    "stitched_mat_kg": "Сшитый материал",
    "ud300_m": "UD300",
    "fiberglass_2400tex_kg": "Стекловолокно 2400tex",
    "sand_kg": "Песок",
    "ud250_m": "UD250",
    "sand_gauze_m": "Марля для песка",
    "gel_time_minutes": "Время гелеобразования",
}


class DuplicateEntry(Exception):
    """Расход по этой трубе и стадии уже вносили."""


async def ensure_no_duplicate_chemistry(
    session: AsyncSession, pipe_id: int, stage: str
) -> None:
    """Не даём внести расход химии по одной трубе и стадии дважды."""
    exists = (
        await session.execute(
            select(ChemistryLog.id).where(
                ChemistryLog.pipe_id == pipe_id,
                ChemistryLog.stage == ChemistryStage(stage),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if exists:
        raise DuplicateEntry(
            "Расход химии по этой трубе и стадии уже внесён. "
            "Чтобы изменить цифры, подайте заявку на исправление — "
            "повторный ввод списал бы сырьё второй раз."
        )


async def ensure_no_duplicate_dry(
    session: AsyncSession, pipe_id: int, stage: str
) -> None:
    """Не даём внести расход сухих материалов дважды."""
    exists = (
        await session.execute(
            select(DryMaterialLog.id).where(
                DryMaterialLog.pipe_id == pipe_id,
                DryMaterialLog.stage == DryMaterialStage(stage),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if exists:
        raise DuplicateEntry(
            "Сухие материалы по этой трубе и стадии уже внесены. "
            "Чтобы изменить цифры, подайте заявку на исправление — "
            "повторный ввод списал бы сырьё второй раз."
        )


async def ensure_no_duplicate_lab(
    session: AsyncSession, pipe_id: int, test_type: str
) -> None:
    """Не даём внести один и тот же тест дважды."""
    exists = (
        await session.execute(
            select(LabTest.id).where(
                LabTest.pipe_id == pipe_id,
                LabTest.test_type == LabTestType(test_type),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if exists:
        raise DuplicateEntry(
            "Такой тест по этой трубе уже вносили. "
            "Чтобы изменить результат, подайте заявку на исправление."
        )


async def _norm_for_pipe(session: AsyncSession, pipe_id: int) -> PipeNorm | None:
    """Находит норматив для типоразмера трубы (или None, если его нет)."""
    # task грузим сразу: в асинхронном режиме ленивая подгрузка связи
    # выбрасывает ошибку (MissingGreenlet).
    pipe = (
        await session.execute(
            select(Pipe).options(selectinload(Pipe.task)).where(Pipe.id == pipe_id)
        )
    ).scalar_one_or_none()
    if pipe is None or pipe.task is None:
        return None
    t = pipe.task
    return (
        await session.execute(
            select(PipeNorm).where(
                PipeNorm.dn == t.dn,
                PipeNorm.pn == t.pn,
                PipeNorm.sn == t.sn,
                PipeNorm.with_sand == t.with_sand,
            )
        )
    ).scalar_one_or_none()


def _compare_with_norm(
    values: dict[str, float | None],
    norm: PipeNorm,
    mapping: dict[str, str],
) -> list[str]:
    """Возвращает список предупреждений об отклонении от нормы."""
    warnings: list[str] = []
    for field, norm_field in mapping.items():
        actual = values.get(field)
        expected = getattr(norm, norm_field, None)
        if actual is None or not expected:
            continue
        if actual > expected * NORM_TOLERANCE or actual < expected / NORM_TOLERANCE:
            label = FIELD_LABELS.get(field, field)
            warnings.append(
                f"{label}: введено {actual:g}, по норме около {expected:g}"
            )
    return warnings


async def check_chemistry_sanity(
    session: AsyncSession, pipe_id: int, stage: str, values: dict
) -> list[str]:
    """Предупреждения по расходу химии: отклонение от нормы и нехватка склада."""
    warnings: list[str] = []

    norm = await _norm_for_pipe(session, pipe_id)
    if norm is not None:
        warnings += _compare_with_norm(
            values, norm, CHEMISTRY_NORM_FIELDS.get(stage, {})
        )

    warnings += await _check_stock(session, values, stage_is_chemistry=True, stage=stage)
    return warnings


async def check_dry_sanity(
    session: AsyncSession, pipe_id: int, stage: str, values: dict
) -> list[str]:
    """Предупреждения по сухим материалам."""
    warnings: list[str] = []

    norm = await _norm_for_pipe(session, pipe_id)
    if norm is not None:
        warnings += _compare_with_norm(values, norm, DRY_NORM_FIELDS.get(stage, {}))

    warnings += await _check_stock(session, values, stage_is_chemistry=False)
    return warnings


async def _check_stock(
    session: AsyncSession,
    values: dict,
    *,
    stage_is_chemistry: bool,
    stage: str = "",
) -> list[str]:
    """Предупреждает, если списываем больше, чем числится на складе."""
    # Импорт здесь, чтобы не было кольцевой зависимости модулей
    from web.services.stock_service import (
        CHEMISTRY_STOCK_MAP,
        DRY_MATERIAL_STOCK_MAP,
    )

    mapping = (
        CHEMISTRY_STOCK_MAP.get(stage, {})
        if stage_is_chemistry
        else DRY_MATERIAL_STOCK_MAP
    )

    warnings: list[str] = []
    for field, (material_name, unit) in mapping.items():
        need = values.get(field)
        if not need:
            continue
        stock = (
            await session.execute(
                select(MaterialStock).where(
                    MaterialStock.material_name == material_name
                )
            )
        ).scalar_one_or_none()
        have = stock.current_quantity if stock else 0.0
        if need > have:
            warnings.append(
                f"{material_name}: списываем {need:g} {unit}, "
                f"на складе {have:g} {unit}"
            )
    return warnings
