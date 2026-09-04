"""
Роуты для Лаборанта — ввод лабораторных тестов.
GET  /lab     — HTML-форма со списком труб
POST /api/lab — сохранение LabTest в БД
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import LabTest, LabTestType, Pipe, PipeStatus, User, UserRole
from web.auth import require_roles
from web.schemas import LabTestCreate

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

LAB_STATUSES = [
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
]


@router.get("/lab", response_class=HTMLResponse)
async def lab_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Отдаёт HTML-форму лабораторных тестов."""
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
async def create_lab_test(
    data: LabTestCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.LAB_TECHNICIAN)),
):
    """Сохраняет запись лабораторного теста в БД."""
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
        entered_by=user.telegram_id,
    )
    session.add(test)

    return {"status": "ok"}
