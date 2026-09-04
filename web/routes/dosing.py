"""
Роуты для Дозировщика — ввод фактического расхода химии.
GET  /dosing     — HTML-форма со списком труб
POST /api/dosing — сохранение ChemistryLog в БД
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import ChemistryLog, ChemistryStage, Pipe, PipeStatus, User, UserRole
from web.auth import require_roles
from web.schemas import ChemistryLogCreate
from web.services.stock_service import deduct_chemistry
from web.services.validation_service import (
    DuplicateEntry,
    check_chemistry_sanity,
    ensure_no_duplicate_chemistry,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DOSING_STATUSES = [
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
]


@router.get("/dosing", response_class=HTMLResponse)
async def dosing_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Отдаёт HTML-форму с выпадающим списком труб."""
    result = await session.execute(
        select(Pipe)
        .where(Pipe.status.in_(DOSING_STATUSES))
        .order_by(Pipe.id)
    )
    pipes = result.scalars().all()

    return templates.TemplateResponse(
        "dosing.html",
        {"request": request, "pipes": pipes},
    )


@router.post("/api/dosing")
async def create_chemistry_log(
    data: ChemistryLogCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.DOSING_OPERATOR)),
):
    """Сохраняет запись расхода химии в БД и списывает со склада."""
    values = {
        "resin_kg": data.resin_kg,
        "cobalt_kg": data.cobalt_kg,
        "peroxide_kg": data.peroxide_kg,
    }

    # Защита 1: не даём внести расход по одной трубе и стадии дважды
    try:
        await ensure_no_duplicate_chemistry(session, data.pipe_id, data.stage)
    except DuplicateEntry as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Защита 2 и 3: отклонение от нормы и нехватка склада — просим подтвердить
    if not data.confirmed:
        warnings = await check_chemistry_sanity(
            session, data.pipe_id, data.stage, values
        )
        if warnings:
            raise HTTPException(
                status_code=422,
                detail={"needs_confirmation": True, "warnings": warnings},
            )

    log = ChemistryLog(
        pipe_id=data.pipe_id,
        stage=ChemistryStage(data.stage),
        resin_kg=data.resin_kg,
        cobalt_kg=data.cobalt_kg,
        peroxide_kg=data.peroxide_kg,
        entered_by=user.telegram_id,
    )
    session.add(log)

    # Автоматически списываем со склада
    await deduct_chemistry(session, data.stage, values)

    return {"status": "ok"}
