"""
Роуты для прихода сырья на склад (Material Receipt).
GET  /receipt     — HTML-форма (Jinja2)
POST /api/receipt — сохранение в БД
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import MaterialReceipt, User, UserRole
from web.auth import require_roles
from web.schemas import ReceiptCreate
from web.services.stock_service import update_stock

router = APIRouter()

# Шаблоны
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/receipt", response_class=HTMLResponse)
async def receipt_page(request: Request):
    """Отдаёт HTML-форму ввода прихода сырья."""
    return templates.TemplateResponse("receipt.html", {"request": request})


@router.post("/api/receipt")
async def create_receipt(
    data: ReceiptCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles(UserRole.SHIFT_LEADER)),
):
    """Сохраняет запись прихода сырья в БД и обновляет склад."""
    receipt = MaterialReceipt(
        material_name=data.material_name,
        quantity=data.quantity,
        unit=data.unit,
        batch_number=data.batch_number,
        entered_by=user.telegram_id,
    )
    session.add(receipt)

    # Автоматически пополняем склад
    await update_stock(session, data.material_name, data.quantity, data.unit)

    return {"status": "ok"}
