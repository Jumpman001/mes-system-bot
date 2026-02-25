"""
Роуты Инженера ОТК — паспорт качества.
GET  /qc                  — HTML-форма
GET  /api/qc/pipe/{id}    — JSON с данными трубы + QCPassport
POST /api/qc              — Upsert QCPassport + бизнес-логика статусов
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.database import async_session
from db.models import FinalVerdict, Pipe, PipeStatus, QCPassport, Task
from web.schemas import QCPassportUpdate, PipeIdentificationCreate

router = APIRouter()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

HIDDEN_STATUSES = {PipeStatus.CREATED, PipeStatus.ACCEPTED, PipeStatus.REJECTED}


@router.get("/qc", response_class=HTMLResponse)
async def qc_page(request: Request):
    async with async_session() as session:
        result = await session.execute(
            select(Pipe).where(Pipe.status.notin_(HIDDEN_STATUSES)).where(Pipe.status != PipeStatus.PENDING_ID).order_by(Pipe.id)
        )
        pipes = result.scalars().all()
    return templates.TemplateResponse("qc.html", {"request": request, "pipes": pipes})


@router.get("/api/qc/pipe/{pipe_id}")
async def get_pipe_qc_data(pipe_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Pipe).options(selectinload(Pipe.task), selectinload(Pipe.qc_passport)).where(Pipe.id == pipe_id)
        )
        pipe = result.scalar_one_or_none()
    if not pipe:
        return {"error": "Труба не найдена"}
    passport_data = None
    if pipe.qc_passport:
        p = pipe.qc_passport
        passport_data = {
            "sand_layer_1_mm": p.sand_layer_1_mm, "sand_layer_2_mm": p.sand_layer_2_mm,
            "turning_approved": p.turning_approved,
            "pipe_circumference_mm": p.pipe_circumference_mm, "bell_circumference_mm": p.bell_circumference_mm,
            "wall_thickness_mm": p.wall_thickness_mm, "bell_wall_thickness_mm": p.bell_wall_thickness_mm,
            "nipple_outer_diameter_mm": p.nipple_outer_diameter_mm,
            "channel_diameter_1_mm": p.channel_diameter_1_mm, "channel_diameter_2_mm": p.channel_diameter_2_mm,
            "channel_depth_mm": p.channel_depth_mm, "channel_width_mm": p.channel_width_mm,
            "machined_length_mm": p.machined_length_mm,
            "visual_inspection_notes": p.visual_inspection_notes,
            "final_verdict": p.final_verdict.value if p.final_verdict else None,
        }
    return {"status": pipe.status.value, "dn": pipe.task.dn if pipe.task else None, "serial_number": pipe.serial_number, "passport": passport_data}


@router.post("/api/qc")
async def upsert_qc_passport(data: QCPassportUpdate):
    now = datetime.now(timezone.utc)
    try:
        async with async_session() as session:
            pipe_result = await session.execute(select(Pipe).where(Pipe.id == data.pipe_id))
            pipe = pipe_result.scalar_one_or_none()
            if not pipe:
                raise HTTPException(status_code=404, detail="Труба не найдена")

            passport_result = await session.execute(select(QCPassport).where(QCPassport.pipe_id == data.pipe_id))
            passport = passport_result.scalar_one_or_none()
            if not passport:
                passport = QCPassport(pipe_id=data.pipe_id)
                session.add(passport)

            update_fields = {
                "sand_layer_1_mm", "sand_layer_2_mm",
                "pipe_circumference_mm", "bell_circumference_mm",
                "wall_thickness_mm", "bell_wall_thickness_mm", "nipple_outer_diameter_mm",
                "channel_diameter_1_mm", "channel_diameter_2_mm",
                "channel_depth_mm", "channel_width_mm", "machined_length_mm",
                "visual_inspection_notes",
            }
            for field in update_fields:
                val = getattr(data, field)
                if val is not None:
                    setattr(passport, field, val)

            if data.turning_approved is not None:
                passport.turning_approved = data.turning_approved
                passport.turning_approved_by = data.telegram_id
                passport.turning_approved_at = now
                if data.turning_approved and pipe.status == PipeStatus.WAITING_QC_APPROVAL:
                    pipe.status = PipeStatus.TURNING

            if data.pipe_circumference_mm is not None or data.outer_dn_mm is not None:
                passport.geometry_entered_by = data.telegram_id
                passport.geometry_entered_at = now

            if data.final_verdict is not None:
                verdict = FinalVerdict(data.final_verdict)
                passport.final_verdict = verdict
                passport.verdict_by = data.telegram_id
                passport.verdict_at = now
                if verdict == FinalVerdict.PASSED:
                    pipe.status = PipeStatus.ACCEPTED
                elif verdict == FinalVerdict.REJECTED:
                    pipe.status = PipeStatus.REJECTED

            await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка при сохранении паспорта ОТК: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}


# ── QC Naming (Присвоение серийных номеров) ──────────────────────────────────

@router.get("/qc_naming", response_class=HTMLResponse)
async def qc_naming_page(request: Request):
    """Страница присвоения серийных номеров трубам со статусом PENDING_ID."""
    async with async_session() as session:
        result = await session.execute(
            select(Pipe)
            .options(selectinload(Pipe.task))
            .where(Pipe.status == PipeStatus.PENDING_ID)
            .order_by(Pipe.id)
        )
        pipes = result.scalars().all()
    return templates.TemplateResponse("qc_naming.html", {"request": request, "pipes": pipes})


@router.post("/api/qc_naming")
async def assign_serial_number(data: PipeIdentificationCreate):
    """Присваивает серийный номер трубе и переводит в статус CREATED."""
    try:
        async with async_session() as session:
            result = await session.execute(select(Pipe).where(Pipe.id == data.pipe_id))
            pipe = result.scalar_one_or_none()
            if not pipe:
                raise HTTPException(status_code=404, detail="Труба не найдена")
            if pipe.status != PipeStatus.PENDING_ID:
                raise HTTPException(status_code=400, detail="Труба не в статусе ожидания идентификации")

            # Проверяем уникальность нового серийного номера
            dup_result = await session.execute(
                select(Pipe).where(Pipe.serial_number == data.new_serial_number, Pipe.id != data.pipe_id)
            )
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Серийный номер уже используется")

            pipe.serial_number = data.new_serial_number
            pipe.status = PipeStatus.CREATED
            await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Ошибка при присвоении серийного номера: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}
