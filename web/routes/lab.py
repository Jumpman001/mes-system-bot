"""
Роуты для Лаборанта — ввод лабораторных тестов.
GET  /lab     — HTML-форма со списком труб
POST /api/lab — сохранение LabTest в БД
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db.database import async_session
from db.models import LabTest, LabTestType, Pipe, PipeStatus
from web.schemas import LabTestCreate

router = APIRouter()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

LAB_STATUSES = [
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
]


@router.get("/lab", response_class=HTMLResponse)
async def lab_page(request: Request):
    """Отдаёт HTML-форму лабораторных тестов."""
    async with async_session() as session:
        result = await session.execute(
            select(Pipe)
            .where(Pipe.status.in_(LAB_STATUSES))
            .order_by(Pipe.id)
        )
        pipes = result.scalars().all()

    return templates.TemplateResponse(
        "lab.html",
        {"request": request, "pipes": pipes},
    )


@router.post("/api/lab")
async def create_lab_test(data: LabTestCreate):
    """Сохраняет запись лабораторного теста в БД."""
    try:
        async with async_session() as session:
            test = LabTest(
                pipe_id=data.pipe_id,
                test_type=LabTestType(data.test_type),
                gel_time_minutes=data.gel_time_minutes,
                room_temperature_c=data.room_temperature_c,
                exothermic_peak_c=data.exothermic_peak_c,
                viscosity_mpa_s=data.viscosity_mpa_s,
                absorbency_result=data.absorbency_result,
                is_homogeneous=data.is_homogeneous,
                theoretical_resin_percent=data.theoretical_resin_percent,
                entered_by=data.telegram_id,
            )
            session.add(test)
            await session.commit()
    except SQLAlchemyError as e:
        logger.error("Ошибка БД при сохранении лаб. теста: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка базы данных.")
    except Exception as e:
        logger.exception("Непредвиденная ошибка при сохранении лаб. теста: %s", e)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

    return {"status": "ok"}
