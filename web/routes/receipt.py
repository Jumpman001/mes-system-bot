"""
Роуты для прихода сырья на склад (Material Receipt).
GET  /receipt     — HTML-форма (Jinja2)
POST /api/receipt — сохранение в БД
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db.database import async_session
from db.models import MaterialReceipt
from web.schemas import ReceiptCreate
from web.services.stock_service import update_stock

router = APIRouter()
logger = logging.getLogger(__name__)

# Шаблоны
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/receipt", response_class=HTMLResponse)
async def receipt_page(request: Request):
    """Отдаёт HTML-форму ввода прихода сырья."""
    return templates.TemplateResponse("receipt.html", {"request": request})


@router.post("/api/receipt")
async def create_receipt(data: ReceiptCreate):
    """Сохраняет запись прихода сырья в БД и обновляет склад."""
    try:
        async with async_session() as session:
            receipt = MaterialReceipt(
                material_name=data.material_name,
                quantity=data.quantity,
                unit=data.unit,
                batch_number=data.batch_number,
                entered_by=data.telegram_id,
            )
            session.add(receipt)

            # Автоматически пополняем склад
            await update_stock(session, data.material_name, data.quantity, data.unit)

            await session.commit()
    except Exception as e:
        logger.error("Ошибка при сохранении прихода: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}
