"""
Заявки на исправление данных.

GET  /my_entries          — экран «мои записи» (что я вносил)
GET  /api/my_entries      — JSON со списком записей текущего работника
POST /api/corrections     — подать заявку на исправление

Применяет заявку только администратор — через бота (см. bot/handlers/corrections.py).
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.utils import format_local_time
from db.database import get_session
from db.models import (
    ChemistryLog,
    CorrectionRequest,
    CorrectionStatus,
    CorrectionTarget,
    DryMaterialLog,
    LabTest,
    MaterialReceipt,
    User,
)
from web.auth import get_current_user
from web.schemas import CorrectionCreate
from web.services.correction_service import EDITABLE_FIELDS, format_value

router = APIRouter()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Сколько последних записей показываем работнику
RECENT_LIMIT = 20

STAGE_LABELS = {
    "liner": "Лайнер",
    "winder": "Виндер",
    "winder_fiberglass": "Виндер — стекловолокно",
    "winder_sand_1": "Виндер — песок 1",
    "winder_sand_2": "Виндер — песок 2",
    "gel_time_liner": "Гелеобразование — лайнер",
    "gel_time_winder": "Гелеобразование — виндер",
    "sand_absorbency": "Впитываемость песка",
}

FIELD_LABELS = {
    "resin_kg": "Смола, кг",
    "cobalt_kg": "Октоат кобальта, кг",
    "peroxide_kg": "Акперокс, кг",
    "polyester_gauze_m": "Полиэфирная марля, м",
    "veil_m": "Вуаль, м",
    "stitched_mat_kg": "Сшитый материал, кг",
    "ud300_m": "UD300, м",
    "fiberglass_2400tex_kg": "Стекловолокно 2400tex, кг",
    "sand_kg": "Песок, кг",
    "ud250_m": "UD250, м",
    "sand_gauze_m": "Марля для песка, м",
    "gel_time_minutes": "Время гелеобразования, мин",
    "room_temperature_c": "Температура в цеху, °C",
    "exothermic_peak_c": "Экзотермический пик, °C",
    "viscosity_mpa_s": "Вязкость, мПа·с",
    "absorbency_result": "Результат впитываемости",
    "is_homogeneous": "Однородность",
    "theoretical_resin_percent": "Теор. содержание смолы, %",
    "quantity": "Количество",
    "batch_number": "Номер партии",
}


@router.get("/my_entries", response_class=HTMLResponse)
async def my_entries_page(request: Request):
    """Экран со списком собственных записей и кнопкой «Исправить»."""
    return templates.TemplateResponse("my_entries.html", {"request": request})


def _entry(target: CorrectionTarget, record, title: str, fields: dict) -> dict:
    """Собирает строку списка записей."""
    return {
        "target": target.value,
        "record_id": record.id,
        "title": title,
        "entered_at": format_local_time(record.entered_at),
        # только непустые поля — работнику незачем видеть пустые строки
        "fields": {k: v for k, v in fields.items() if v is not None},
        "labels": FIELD_LABELS,
    }


@router.get("/api/my_entries")
async def get_my_entries(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Возвращает последние записи, которые внёс текущий работник."""
    entries: list[dict] = []
    me = user.telegram_id

    chem = (await session.execute(
        select(ChemistryLog)
        .options(selectinload(ChemistryLog.pipe))
        .where(ChemistryLog.entered_by == me)
        .order_by(ChemistryLog.id.desc()).limit(RECENT_LIMIT)
    )).scalars().all()
    for c in chem:
        serial = c.pipe.serial_number if c.pipe else f"#{c.pipe_id}"
        entries.append(_entry(
            CorrectionTarget.CHEMISTRY, c,
            f"{serial} · {STAGE_LABELS.get(c.stage.value, c.stage.value)}",
            {"resin_kg": c.resin_kg, "cobalt_kg": c.cobalt_kg,
             "peroxide_kg": c.peroxide_kg},
        ))

    dry = (await session.execute(
        select(DryMaterialLog)
        .options(selectinload(DryMaterialLog.pipe))
        .where(DryMaterialLog.entered_by == me)
        .order_by(DryMaterialLog.id.desc()).limit(RECENT_LIMIT)
    )).scalars().all()
    for d in dry:
        serial = d.pipe.serial_number if d.pipe else f"#{d.pipe_id}"
        entries.append(_entry(
            CorrectionTarget.DRY_MATERIAL, d,
            f"{serial} · {STAGE_LABELS.get(d.stage.value, d.stage.value)}",
            {"polyester_gauze_m": d.polyester_gauze_m, "veil_m": d.veil_m,
             "stitched_mat_kg": d.stitched_mat_kg, "ud300_m": d.ud300_m,
             "fiberglass_2400tex_kg": d.fiberglass_2400tex_kg,
             "sand_kg": d.sand_kg, "ud250_m": d.ud250_m,
             "sand_gauze_m": d.sand_gauze_m},
        ))

    lab = (await session.execute(
        select(LabTest)
        .options(selectinload(LabTest.pipe))
        .where(LabTest.entered_by == me)
        .order_by(LabTest.id.desc()).limit(RECENT_LIMIT)
    )).scalars().all()
    for t in lab:
        serial = t.pipe.serial_number if t.pipe else f"#{t.pipe_id}"
        entries.append(_entry(
            CorrectionTarget.LAB_TEST, t,
            f"{serial} · {STAGE_LABELS.get(t.test_type.value, t.test_type.value)}",
            {"gel_time_minutes": t.gel_time_minutes,
             "room_temperature_c": t.room_temperature_c,
             "exothermic_peak_c": t.exothermic_peak_c,
             "viscosity_mpa_s": t.viscosity_mpa_s,
             "absorbency_result": t.absorbency_result,
             "is_homogeneous": t.is_homogeneous,
             "theoretical_resin_percent": t.theoretical_resin_percent},
        ))

    receipts = (await session.execute(
        select(MaterialReceipt)
        .where(MaterialReceipt.entered_by == me)
        .order_by(MaterialReceipt.id.desc()).limit(RECENT_LIMIT)
    )).scalars().all()
    for r in receipts:
        entries.append(_entry(
            CorrectionTarget.RECEIPT, r,
            f"Приход · {r.material_name}",
            {"quantity": r.quantity, "batch_number": r.batch_number},
        ))

    entries.sort(key=lambda e: e["entered_at"], reverse=True)

    # Заявки, которые уже на рассмотрении — чтобы не подавали повторно
    pending = (await session.execute(
        select(CorrectionRequest).where(
            CorrectionRequest.requested_by == me,
            CorrectionRequest.status == CorrectionStatus.PENDING,
        )
    )).scalars().all()

    return {
        "entries": entries,
        "pending": [
            {"target": p.target.value, "record_id": p.record_id,
             "field_name": p.field_name, "new_value": p.new_value}
            for p in pending
        ],
    }


@router.post("/api/corrections")
async def create_correction(
    data: CorrectionCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Подать заявку на исправление своей записи."""
    try:
        target = CorrectionTarget(data.target)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестный тип записи.")

    if data.field_name not in EDITABLE_FIELDS[target]:
        raise HTTPException(
            status_code=400,
            detail=f"Поле «{data.field_name}» исправлять нельзя.",
        )

    reason = (data.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(
            status_code=400,
            detail="Опишите причину исправления — она уйдёт администратору.",
        )

    # Одна открытая заявка на поле: иначе админ получит пачку дублей
    duplicate = (await session.execute(
        select(CorrectionRequest.id).where(
            CorrectionRequest.target == target,
            CorrectionRequest.record_id == data.record_id,
            CorrectionRequest.field_name == data.field_name,
            CorrectionRequest.status == CorrectionStatus.PENDING,
        ).limit(1)
    )).scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Заявка по этому полю уже отправлена и ждёт решения.",
        )

    # Текущее значение сохраняем как «было» — это и есть журнал
    from web.services.correction_service import TARGET_MODELS
    model = TARGET_MODELS[target]
    record = (await session.execute(
        select(model).where(model.id == data.record_id)
    )).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")

    old_value = format_value(getattr(record, data.field_name, None))

    request_row = CorrectionRequest(
        target=target,
        record_id=data.record_id,
        field_name=data.field_name,
        old_value=old_value,
        new_value=data.new_value,
        reason=reason,
        requested_by=user.telegram_id,
        status=CorrectionStatus.PENDING,
    )
    session.add(request_row)
    await session.flush()  # нужен id для уведомления администратору

    logger.info(
        "Заявка на исправление #%s: %s.%s (запись %s) %s → %s, от %s",
        request_row.id, target.value, data.field_name, data.record_id,
        old_value, data.new_value, user.telegram_id,
    )

    # Сообщаем администраторам — с кнопками «Одобрить» / «Отклонить»
    from bot.notify import notify_correction_request
    await notify_correction_request(
        session,
        request_id=request_row.id,
        author_name=user.full_name,
        title=f"{target.value} #{data.record_id}",
        field_label=FIELD_LABELS.get(data.field_name, data.field_name),
        old_value=old_value,
        new_value=data.new_value,
        reason=reason,
    )

    return {"status": "ok", "request_id": request_row.id}
