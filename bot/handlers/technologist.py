"""
Хэндлер Технолога — команда /dry_materials для открытия Mini App.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from core.config import settings

router = Router(name="technologist")


@router.message(Command("dry_materials"))
async def cmd_dry_materials(message: Message) -> None:
    """Отправляет кнопку Mini App для ввода сухих материалов."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🧵 Открыть форму",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/dry_materials"),
        )]
    ])
    await message.answer(
        "🧵 <b>Ввод фактического расхода сухих материалов</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть форму ввода.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
