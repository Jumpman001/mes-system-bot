"""
Роуты для Технолога — ввод фактического расхода сухих материалов.
GET  /dry_materials     — HTML-форма со списком труб
POST /api/dry_materials — сохранение DryMaterialLog в БД
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import DryMaterialLog, DryMaterialStage, Pipe, PipeStatus, User, UserRole
from web.auth import require_roles
from web.schemas import DryMaterialLogCreate
from web.services.stock_service import deduct_dry_materials
from web.services.validation_service import (
    DuplicateEntry,
    check_dry_sanity,
    ensure_no_duplicate_dry,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

TECH_STATUSES = [
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
]


@router.get("/dry_materials", response_class=HTMLResponse)
async def dry_materials_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Отдаёт HTML-форму с выпадающим списком труб."""
    result = await session.execute(
        select(Pipe)
        .where(Pipe.status.in_(TECH_STATUSES))
        .order_by(Pipe.id)
    )
    pipes = result.scalars().all()

    return templates.TemplateResponse(
        "technologist.html",
        {"request": request, "pipes": pipes},
    )


@router.post("/api/dry_materials")
async def create_dry_material_log(
    data: DryMaterialLogCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.TECHNOLOGIST)),
):
    """Сохраняет запись расхода сухих материалов в БД и списывает со склада."""
    values = {
        "polyester_gauze_m": data.polyester_gauze_m,
        "veil_m": data.veil_m,
        "stitched_mat_kg": data.stitched_mat_kg,
        "ud300_m": data.ud300_m,
        "fiberglass_2400tex_kg": data.fiberglass_2400tex_kg,
        "sand_kg": data.sand_kg,
        "ud250_m": data.ud250_m,
        "sand_gauze_m": data.sand_gauze_m,
    }

    # Защита 1: повторный ввод по той же трубе и стадии
    try:
        await ensure_no_duplicate_dry(session, data.pipe_id, data.stage)
    except DuplicateEntry as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Защита 2 и 3: отклонение от нормы и нехватка склада
    if not data.confirmed:
        warnings = await check_dry_sanity(session, data.pipe_id, data.stage, values)
        if warnings:
            raise HTTPException(
                status_code=422,
                detail={"needs_confirmation": True, "warnings": warnings},
            )

    log = DryMaterialLog(
        pipe_id=data.pipe_id,
        stage=DryMaterialStage(data.stage),
        polyester_gauze_m=data.polyester_gauze_m,
        veil_m=data.veil_m,
        stitched_mat_kg=data.stitched_mat_kg,
        ud300_m=data.ud300_m,
        fiberglass_2400tex_kg=data.fiberglass_2400tex_kg,
        sand_kg=data.sand_kg,
        ud250_m=data.ud250_m,
        sand_gauze_m=data.sand_gauze_m,
        entered_by=user.telegram_id,
    )
    session.add(log)

    # Автоматически списываем со склада
    await deduct_dry_materials(session, values)

    return {"status": "ok"}
