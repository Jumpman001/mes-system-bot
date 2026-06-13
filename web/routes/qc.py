"""
Роуты Инженера ОТК — паспорт качества.
GET  /qc                  — HTML-форма
GET  /api/qc/pipe/{id}    — JSON с данными трубы + QCPassport
POST /api/qc              — Upsert QCPassport + бизнес-логика статусов
"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from core.workflow import next_status_after_qc_approval, verdict_to_status
from db.database import get_session
from db.models import FinalVerdict, Pipe, PipeStatus, QCPassport, User, UserRole
from web.auth import require_roles
from web.schemas import (
    PipeIdentificationCreate,
    PipeQCData,
    QCPassportData,
    QCPassportUpdate,
)

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

HIDDEN_STATUSES = {PipeStatus.CREATED, PipeStatus.ACCEPTED, PipeStatus.REJECTED}

# Поля паспорта, которые обновляются напрямую из тела запроса (если не None)
QC_UPDATE_FIELDS = {
    "sand_layer_1_mm", "sand_layer_2_mm",
    "pipe_circumference_mm", "bell_circumference_mm",
    "wall_thickness_mm", "bell_wall_thickness_mm", "nipple_outer_diameter_mm",
    "channel_diameter_1_mm", "channel_diameter_2_mm",
    "channel_depth_mm", "channel_width_mm", "machined_length_mm",
    "visual_inspection_notes",
}


@router.get("/qc", response_class=HTMLResponse)
async def qc_page(request: Request, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Pipe)
        .where(Pipe.status.notin_(HIDDEN_STATUSES))
        .where(Pipe.status != PipeStatus.PENDING_ID)
        .order_by(Pipe.id)
    )
    pipes = result.scalars().all()
    return templates.TemplateResponse("qc.html", {"request": request, "pipes": pipes})


@router.get("/api/qc/pipe/{pipe_id}")
async def get_pipe_qc_data(pipe_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Pipe)
        .options(selectinload(Pipe.task), selectinload(Pipe.qc_passport))
        .where(Pipe.id == pipe_id)
    )
    pipe = result.scalar_one_or_none()
    if not pipe:
        return {"error": "Труба не найдена"}

    passport = (
        QCPassportData.model_validate(pipe.qc_passport)
        if pipe.qc_passport else None
    )
    return PipeQCData(
        status=pipe.status.value,
        dn=pipe.task.dn if pipe.task else None,
        serial_number=pipe.serial_number,
        passport=passport,
    ).model_dump(mode="json")


@router.post("/api/qc")
async def upsert_qc_passport(
    data: QCPassportUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.QC_ENGINEER)),
):
    now = datetime.now(timezone.utc)

    pipe = (
        await session.execute(select(Pipe).where(Pipe.id == data.pipe_id))
    ).scalar_one_or_none()
    if not pipe:
        raise HTTPException(status_code=404, detail="Труба не найдена")

    passport = (
        await session.execute(
            select(QCPassport).where(QCPassport.pipe_id == data.pipe_id)
        )
    ).scalar_one_or_none()
    if not passport:
        passport = QCPassport(pipe_id=data.pipe_id)
        session.add(passport)

    for field in QC_UPDATE_FIELDS:
        val = getattr(data, field)
        if val is not None:
            setattr(passport, field, val)

    if data.turning_approved is not None:
        passport.turning_approved = data.turning_approved
        passport.turning_approved_by = user.telegram_id
        passport.turning_approved_at = now
        if data.turning_approved:
            new_status = next_status_after_qc_approval(pipe.status)
            if new_status:
                pipe.status = new_status

    if data.pipe_circumference_mm is not None or data.outer_dn_mm is not None:
        passport.geometry_entered_by = user.telegram_id
        passport.geometry_entered_at = now

    if data.final_verdict is not None:
        verdict = FinalVerdict(data.final_verdict)
        passport.final_verdict = verdict
        passport.verdict_by = user.telegram_id
        passport.verdict_at = now
        pipe.status = verdict_to_status(verdict)

    return {"status": "ok"}


# ── QC Naming (Присвоение серийных номеров) ──────────────────────────────────

@router.get("/qc_naming", response_class=HTMLResponse)
async def qc_naming_page(request: Request, session: AsyncSession = Depends(get_session)):
    """Страница присвоения серийных номеров трубам со статусом PENDING_ID."""
    result = await session.execute(
        select(Pipe)
        .options(selectinload(Pipe.task))
        .where(Pipe.status == PipeStatus.PENDING_ID)
        .order_by(Pipe.id)
    )
    pipes = result.scalars().all()
    return templates.TemplateResponse("qc_naming.html", {"request": request, "pipes": pipes})


@router.post("/api/qc_naming")
async def assign_serial_number(
    data: PipeIdentificationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.QC_ENGINEER)),
):
    """Присваивает серийный номер трубе и переводит в статус CREATED."""
    pipe = (
        await session.execute(select(Pipe).where(Pipe.id == data.pipe_id))
    ).scalar_one_or_none()
    if not pipe:
        raise HTTPException(status_code=404, detail="Труба не найдена")
    if pipe.status != PipeStatus.PENDING_ID:
        raise HTTPException(status_code=400, detail="Труба не в статусе ожидания идентификации")

    # Проверяем уникальность нового серийного номера
    dup = (
        await session.execute(
            select(Pipe).where(
                Pipe.serial_number == data.new_serial_number,
                Pipe.id != data.pipe_id,
            )
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=400, detail="Серийный номер уже используется")

    pipe.serial_number = data.new_serial_number
    pipe.status = PipeStatus.CREATED

    return {"status": "ok"}
