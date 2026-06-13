"""
Роуты для Склада — текущие остатки материалов.
GET  /inventory     — HTML-страница (Mini App)
GET  /api/inventory — JSON с остатками
POST /api/inventory/min — обновить минимальный порог
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import MaterialStock, User, UserRole
from web.auth import require_roles

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, session: AsyncSession = Depends(get_session)):
    """Отдаёт HTML-страницу склада."""
    result = await session.execute(
        select(MaterialStock).order_by(MaterialStock.material_name)
    )
    items = result.scalars().all()

    stock_list = []
    for item in items:
        # Определяем статус: зелёный / жёлтый / красный
        if item.min_quantity > 0 and item.current_quantity <= item.min_quantity:
            status = "red"
        elif item.min_quantity > 0 and item.current_quantity <= item.min_quantity * 1.5:
            status = "yellow"
        else:
            status = "green"

        stock_list.append({
            "id": item.id,
            "name": item.material_name,
            "quantity": round(item.current_quantity, 2),
            "unit": item.unit,
            "min_quantity": round(item.min_quantity, 2),
            "status": status,
        })

    return templates.TemplateResponse(
        "inventory.html",
        {"request": request, "stock": stock_list},
    )


@router.get("/api/inventory")
async def get_inventory(session: AsyncSession = Depends(get_session)):
    """JSON-список остатков для бота или внешних интеграций."""
    result = await session.execute(
        select(MaterialStock).order_by(MaterialStock.material_name)
    )
    items = result.scalars().all()

    return [
        {
            "material_name": i.material_name,
            "current_quantity": round(i.current_quantity, 2),
            "unit": i.unit,
            "min_quantity": round(i.min_quantity, 2),
            "low_stock": i.min_quantity > 0 and i.current_quantity <= i.min_quantity,
        }
        for i in items
    ]


class MinQuantityUpdate(BaseModel):
    material_id: int
    min_quantity: float


@router.post("/api/inventory/min")
async def update_min_quantity(
    data: MinQuantityUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.SHIFT_LEADER)),
):
    """Обновить минимальный порог материала."""
    await session.execute(
        update(MaterialStock)
        .where(MaterialStock.id == data.material_id)
        .values(min_quantity=data.min_quantity)
    )

    return {"status": "ok"}
