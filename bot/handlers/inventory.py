"""
Хэндлер склада — команда /stock для просмотра остатков материалов.
"""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from core.config import settings
from db.database import async_session
from db.models import MaterialStock
from sqlalchemy import select

router = Router(name="inventory")
logger = logging.getLogger(__name__)


@router.message(Command("stock"))
async def cmd_stock(message: Message) -> None:
    """Показывает остатки склада — текст + кнопка на Mini App."""

    async with async_session() as session:
        result = await session.execute(
            select(MaterialStock).order_by(MaterialStock.material_name)
        )
        items = result.scalars().all()

    if not items:
        await message.answer(
            "📦 <b>Склад пуст</b>\n\n"
            "Данные появятся после первого прихода сырья.",
            parse_mode="HTML",
        )
        return

    # Формируем текстовый отчёт
    lines = ["🏭 <b>Остатки склада</b>\n"]
    low_count = 0

    for item in items:
        qty = round(item.current_quantity, 2)

        if item.min_quantity > 0 and item.current_quantity <= item.min_quantity:
            icon = "🔴"
            low_count += 1
        elif item.min_quantity > 0 and item.current_quantity <= item.min_quantity * 1.5:
            icon = "🟡"
        else:
            icon = "🟢"

        lines.append(f"{icon} {item.material_name}: <b>{qty}</b> {item.unit}")

    if low_count > 0:
        lines.append(f"\n⚠️ <b>{low_count} материал(ов) мало на складе!</b>")

    # Кнопка на Mini App
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Подробнее (склад)",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/inventory"),
        )]
    ])

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
