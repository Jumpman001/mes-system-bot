"""
Роуты для Дозировщика — ввод фактического расхода химии.
GET  /dosing     — HTML-форма со списком труб
POST /api/dosing — сохранение ChemistryLog в БД
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from db.database import async_session
from db.models import ChemistryLog, ChemistryStage, Pipe, PipeStatus
from web.schemas import ChemistryLogCreate
from web.services.stock_service import deduct_chemistry

router = APIRouter()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

DOSING_STATUSES = [
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
]


@router.get("/dosing", response_class=HTMLResponse)
async def dosing_page(request: Request):
    """Отдаёт HTML-форму с выпадающим списком труб."""
    async with async_session() as session:
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
async def create_chemistry_log(data: ChemistryLogCreate):
    """Сохраняет запись расхода химии в БД и списывает со склада."""
    try:
        async with async_session() as session:
            log = ChemistryLog(
                pipe_id=data.pipe_id,
                stage=ChemistryStage(data.stage),
                resin_kg=data.resin_kg,
                cobalt_kg=data.cobalt_kg,
                peroxide_kg=data.peroxide_kg,
                entered_by=data.telegram_id,
            )
            session.add(log)

            # Автоматически списываем со склада
            await deduct_chemistry(session, data.stage, {
                "resin_kg": data.resin_kg,
                "cobalt_kg": data.cobalt_kg,
                "peroxide_kg": data.peroxide_kg,
            })

            await session.commit()
    except Exception as e:
        logger.error("Ошибка при сохранении расхода химии: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}
