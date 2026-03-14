"""
Роуты для Технолога — ввод фактического расхода сухих материалов.
GET  /dry_materials     — HTML-форма со списком труб
POST /api/dry_materials — сохранение DryMaterialLog в БД
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.database import async_session
from db.models import DryMaterialLog, DryMaterialStage, Pipe, PipeStatus
from web.schemas import DryMaterialLogCreate
from web.services.stock_service import deduct_dry_materials

router = APIRouter()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

TECH_STATUSES = [
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
]


@router.get("/dry_materials", response_class=HTMLResponse)
async def dry_materials_page(request: Request):
    """Отдаёт HTML-форму с выпадающим списком труб."""
    async with async_session() as session:
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
async def create_dry_material_log(data: DryMaterialLogCreate):
    """Сохраняет запись расхода сухих материалов в БД и списывает со склада."""
    try:
        async with async_session() as session:
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
                entered_by=data.telegram_id,
            )
            session.add(log)

            # Автоматически списываем со склада
            await deduct_dry_materials(session, {
                "polyester_gauze_m": data.polyester_gauze_m,
                "veil_m": data.veil_m,
                "stitched_mat_kg": data.stitched_mat_kg,
                "ud300_m": data.ud300_m,
                "fiberglass_2400tex_kg": data.fiberglass_2400tex_kg,
                "sand_kg": data.sand_kg,
                "ud250_m": data.ud250_m,
                "sand_gauze_m": data.sand_gauze_m,
            })

            await session.commit()
    except SQLAlchemyError as e:
        logger.error("Ошибка БД при сохранении сухих материалов: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка базы данных.")
    except Exception as e:
        logger.exception("Непредвиденная ошибка при сохранении сухих материалов: %s", e)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

    return {"status": "ok"}
