"""
Роуты аналитики — дашборд для Администратора.
GET /analytics — HTML с KPI карточками и таблицами расхода.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func, select

from db.database import async_session
from db.models import ChemistryLog, DryMaterialLog, Pipe, PipeStatus

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Дашборд аналитики — сводка по производству."""
    async with async_session() as session:
        # ── Статусы труб ─────────────────────────────────────────────
        status_result = await session.execute(
            select(Pipe.status, func.count(Pipe.id)).group_by(Pipe.status)
        )
        status_counts = dict(status_result.all())

        accepted = status_counts.get(PipeStatus.ACCEPTED, 0)
        rejected = status_counts.get(PipeStatus.REJECTED, 0)
        created = status_counts.get(PipeStatus.CREATED, 0)
        total = sum(status_counts.values())
        in_production = total - accepted - rejected - created

        # ── Расход химии (суммы) ─────────────────────────────────────
        chem_result = await session.execute(
            select(
                func.coalesce(func.sum(ChemistryLog.resin_kg), 0),
                func.coalesce(func.sum(ChemistryLog.cobalt_kg), 0),
                func.coalesce(func.sum(ChemistryLog.peroxide_kg), 0),
            )
        )
        chem = chem_result.one()
        chemistry = {
            "resin_kg": round(float(chem[0]), 2),
            "cobalt_kg": round(float(chem[1]), 2),
            "peroxide_kg": round(float(chem[2]), 2),
        }

        # ── Расход сухих материалов (суммы) ──────────────────────────
        dry_result = await session.execute(
            select(
                func.coalesce(func.sum(DryMaterialLog.polyester_gauze_m), 0),
                func.coalesce(func.sum(DryMaterialLog.veil_m), 0),
                func.coalesce(func.sum(DryMaterialLog.stitched_mat_kg), 0),
                func.coalesce(func.sum(DryMaterialLog.ud300_m), 0),
                func.coalesce(func.sum(DryMaterialLog.fiberglass_2400tex_kg), 0),
                func.coalesce(func.sum(DryMaterialLog.sand_kg), 0),
                func.coalesce(func.sum(DryMaterialLog.ud250_m), 0),
                func.coalesce(func.sum(DryMaterialLog.sand_gauze_m), 0),
            )
        )
        dry = dry_result.one()
        dry_materials = {
            "polyester_gauze_m": round(float(dry[0]), 2),
            "veil_m": round(float(dry[1]), 2),
            "stitched_mat_kg": round(float(dry[2]), 2),
            "ud300_m": round(float(dry[3]), 2),
            "fiberglass_2400tex_kg": round(float(dry[4]), 2),
            "sand_kg": round(float(dry[5]), 2),
            "ud250_m": round(float(dry[6]), 2),
            "sand_gauze_m": round(float(dry[7]), 2),
        }

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "accepted": accepted,
            "rejected": rejected,
            "in_production": in_production,
            "total": total,
            "chemistry": chemistry,
            "dry_materials": dry_materials,
        },
    )
