"""
Применение одобренных исправлений.

Ключевой момент — склад пересчитывается на РАЗНИЦУ. Если было списано
100 кг, а правильно 10 кг, склад получает обратно 90 кг. Повторного
списания не происходит: именно этой ошибки мы и избегаем.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ChemistryLog,
    CorrectionRequest,
    CorrectionStatus,
    CorrectionTarget,
    DryMaterialLog,
    LabTest,
    MaterialReceipt,
    QCPassport,
)
from web.services.stock_service import (
    CHEMISTRY_STOCK_MAP,
    DRY_MATERIAL_STOCK_MAP,
    update_stock,
)

logger = logging.getLogger(__name__)

# Модель для каждого типа заявки
TARGET_MODELS = {
    CorrectionTarget.CHEMISTRY: ChemistryLog,
    CorrectionTarget.DRY_MATERIAL: DryMaterialLog,
    CorrectionTarget.LAB_TEST: LabTest,
    CorrectionTarget.RECEIPT: MaterialReceipt,
    CorrectionTarget.QC_PASSPORT: QCPassport,
}

# Какие поля можно исправлять — белый список. Так работник не сможет
# подменить, например, автора записи или привязку к трубе.
EDITABLE_FIELDS: dict[CorrectionTarget, set[str]] = {
    CorrectionTarget.CHEMISTRY: {"resin_kg", "cobalt_kg", "peroxide_kg"},
    CorrectionTarget.DRY_MATERIAL: {
        "polyester_gauze_m", "veil_m", "stitched_mat_kg", "ud300_m",
        "fiberglass_2400tex_kg", "sand_kg", "ud250_m", "sand_gauze_m",
    },
    CorrectionTarget.LAB_TEST: {
        "gel_time_minutes", "room_temperature_c", "exothermic_peak_c",
        "viscosity_mpa_s", "absorbency_result", "is_homogeneous",
        "theoretical_resin_percent",
    },
    CorrectionTarget.RECEIPT: {"quantity", "batch_number"},
    CorrectionTarget.QC_PASSPORT: {
        "sand_layer_1_mm", "sand_layer_2_mm", "pipe_circumference_mm",
        "bell_circumference_mm", "wall_thickness_mm", "bell_wall_thickness_mm",
        "nipple_outer_diameter_mm", "channel_diameter_1_mm",
        "channel_diameter_2_mm", "channel_depth_mm", "channel_width_mm",
        "machined_length_mm", "visual_inspection_notes",
    },
}

# Поля, которые НЕ являются числами (их не приводим к float)
TEXT_FIELDS = {"absorbency_result", "batch_number", "visual_inspection_notes"}
BOOL_FIELDS = {"is_homogeneous"}


def parse_value(field: str, raw: str | None):
    """Приводит сохранённое текстом значение к типу поля."""
    if raw is None or raw == "":
        return None
    if field in BOOL_FIELDS:
        return raw.lower() in ("true", "1", "да")
    if field in TEXT_FIELDS:
        return raw
    return float(raw)


def format_value(value) -> str | None:
    """Готовит значение к хранению в заявке (текстом)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


async def _adjust_stock_for_delta(
    session: AsyncSession,
    target: CorrectionTarget,
    record,
    field: str,
    old_value,
    new_value,
) -> None:
    """
    Возвращает или дописывает на склад разницу между старым и новым.

    Расход: если стало меньше — сырьё возвращается на склад.
    Приход: если стало меньше — лишнее снимается со склада.
    """
    old_num = old_value if isinstance(old_value, (int, float)) else 0.0
    new_num = new_value if isinstance(new_value, (int, float)) else 0.0
    delta = new_num - old_num
    if delta == 0:
        return

    if target == CorrectionTarget.CHEMISTRY:
        mapping = CHEMISTRY_STOCK_MAP.get(record.stage.value, {})
        entry = mapping.get(field)
        if entry:
            name, unit = entry
            # расход вырос → списываем ещё; расход упал → возвращаем
            await update_stock(session, name, -delta, unit)

    elif target == CorrectionTarget.DRY_MATERIAL:
        entry = DRY_MATERIAL_STOCK_MAP.get(field)
        if entry:
            name, unit = entry
            await update_stock(session, name, -delta, unit)

    elif target == CorrectionTarget.RECEIPT and field == "quantity":
        # приход вырос → добавляем; приход упал → снимаем
        await update_stock(session, record.material_name, delta, record.unit)


async def apply_correction(
    session: AsyncSession, request: CorrectionRequest, admin_id: int
) -> None:
    """
    Применяет одобренную заявку: меняет поле и пересчитывает склад.
    Вызывающий код должен убедиться, что заявка ещё в статусе PENDING.
    """
    model = TARGET_MODELS[request.target]
    record = (
        await session.execute(select(model).where(model.id == request.record_id))
    ).scalar_one_or_none()
    if record is None:
        raise ValueError("Исправляемая запись не найдена — возможно, её удалили.")

    if request.field_name not in EDITABLE_FIELDS[request.target]:
        raise ValueError(f"Поле «{request.field_name}» нельзя исправлять.")

    old_value = getattr(record, request.field_name)
    new_value = parse_value(request.field_name, request.new_value)

    setattr(record, request.field_name, new_value)

    await _adjust_stock_for_delta(
        session, request.target, record, request.field_name, old_value, new_value
    )

    request.status = CorrectionStatus.APPROVED
    request.reviewed_by = admin_id
    request.reviewed_at = datetime.now(timezone.utc)

    logger.info(
        "Исправление #%s применено: %s.%s (запись %s): %s → %s",
        request.id, request.target.value, request.field_name,
        request.record_id, request.old_value, request.new_value,
    )


async def reject_correction(
    session: AsyncSession,
    request: CorrectionRequest,
    admin_id: int,
    comment: str | None = None,
) -> None:
    """Отклоняет заявку. Данные остаются как были."""
    request.status = CorrectionStatus.REJECTED
    request.reviewed_by = admin_id
    request.reviewed_at = datetime.now(timezone.utc)
    request.review_comment = comment
    logger.info("Исправление #%s отклонено администратором %s", request.id, admin_id)
