"""
Роуты для Нормативов — таблица норм расхода на тип трубы.
GET  /norms              — HTML-страница (Mini App)
POST /api/norms          — добавить/обновить норматив
GET  /api/norms/{dn}/{pn}/{sn} — получить норматив
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from db.database import async_session
from db.models import PipeNorm

router = APIRouter()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class PipeNormCreate(BaseModel):
    """Схема создания / обновления норматива."""
    dn: int
    pn: int
    sn: int
    with_sand: bool = True

    # Химия
    resin_liner_kg: float | None = None
    resin_winder_kg: float | None = None
    resin_sand_kg: float | None = None
    cobalt_kg: float | None = None
    peroxide_kg: float | None = None

    # Сухие
    polyester_gauze_m: float | None = None
    veil_m: float | None = None
    stitched_mat_kg: float | None = None
    ud300_m: float | None = None
    fiberglass_2400tex_kg: float | None = None
    sand_kg: float | None = None
    ud250_m: float | None = None
    sand_gauze_m: float | None = None

    # Геометрия
    wall_thickness_min_mm: float | None = None
    wall_thickness_max_mm: float | None = None


@router.get("/norms", response_class=HTMLResponse)
async def norms_page(request: Request):
    """Отдаёт HTML-страницу нормативов."""
    async with async_session() as session:
        result = await session.execute(
            select(PipeNorm).order_by(PipeNorm.dn, PipeNorm.pn, PipeNorm.sn)
        )
        norms = result.scalars().all()

    norms_list = []
    for n in norms:
        norms_list.append({
            "id": n.id,
            "dn": n.dn, "pn": n.pn, "sn": n.sn,
            "with_sand": n.with_sand,
            "resin_liner_kg": n.resin_liner_kg,
            "resin_winder_kg": n.resin_winder_kg,
            "resin_sand_kg": n.resin_sand_kg,
            "cobalt_kg": n.cobalt_kg,
            "peroxide_kg": n.peroxide_kg,
            "polyester_gauze_m": n.polyester_gauze_m,
            "veil_m": n.veil_m,
            "stitched_mat_kg": n.stitched_mat_kg,
            "ud300_m": n.ud300_m,
            "fiberglass_2400tex_kg": n.fiberglass_2400tex_kg,
            "sand_kg": n.sand_kg,
            "ud250_m": n.ud250_m,
            "sand_gauze_m": n.sand_gauze_m,
            "wall_thickness_min_mm": n.wall_thickness_min_mm,
            "wall_thickness_max_mm": n.wall_thickness_max_mm,
        })

    return templates.TemplateResponse(
        "norms.html",
        {"request": request, "norms": norms_list},
    )


@router.post("/api/norms")
async def create_or_update_norm(data: PipeNormCreate):
    """Создаёт или обновляет норматив для типа трубы."""
    try:
        async with async_session() as session:
            # Проверяем, есть ли уже норматив для этого типа
            result = await session.execute(
                select(PipeNorm).where(
                    PipeNorm.dn == data.dn,
                    PipeNorm.pn == data.pn,
                    PipeNorm.sn == data.sn,
                    PipeNorm.with_sand == data.with_sand,
                )
            )
            norm = result.scalar_one_or_none()

            if norm:
                # Обновляем
                for field, value in data.model_dump(exclude={"dn", "pn", "sn", "with_sand"}).items():
                    if value is not None:
                        setattr(norm, field, value)
                logger.info("Норматив обновлён: DN%d PN%d SN%d", data.dn, data.pn, data.sn)
            else:
                # Создаём новый
                norm = PipeNorm(**data.model_dump())
                session.add(norm)
                logger.info("Норматив создан: DN%d PN%d SN%d", data.dn, data.pn, data.sn)

            await session.commit()
    except Exception as e:
        logger.error("Ошибка при сохранении норматива: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}


@router.get("/api/norms/{dn}/{pn}/{sn}")
async def get_norm(dn: int, pn: int, sn: int, with_sand: bool = True):
    """Получить норматив для конкретного типа трубы."""
    async with async_session() as session:
        result = await session.execute(
            select(PipeNorm).where(
                PipeNorm.dn == dn,
                PipeNorm.pn == pn,
                PipeNorm.sn == sn,
                PipeNorm.with_sand == with_sand,
            )
        )
        norm = result.scalar_one_or_none()

    if not norm:
        raise HTTPException(status_code=404, detail="Норматив не найден")

    return {
        "dn": norm.dn, "pn": norm.pn, "sn": norm.sn,
        "with_sand": norm.with_sand,
        "resin_liner_kg": norm.resin_liner_kg,
        "resin_winder_kg": norm.resin_winder_kg,
        "resin_sand_kg": norm.resin_sand_kg,
        "cobalt_kg": norm.cobalt_kg,
        "peroxide_kg": norm.peroxide_kg,
        "polyester_gauze_m": norm.polyester_gauze_m,
        "veil_m": norm.veil_m,
        "stitched_mat_kg": norm.stitched_mat_kg,
        "ud300_m": norm.ud300_m,
        "fiberglass_2400tex_kg": norm.fiberglass_2400tex_kg,
        "sand_kg": norm.sand_kg,
        "ud250_m": norm.ud250_m,
        "sand_gauze_m": norm.sand_gauze_m,
        "wall_thickness_min_mm": norm.wall_thickness_min_mm,
        "wall_thickness_max_mm": norm.wall_thickness_max_mm,
    }
