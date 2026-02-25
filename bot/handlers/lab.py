"""
Хэндлер Лаборанта — команда /lab для открытия Mini App.
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

router = Router(name="lab")


@router.message(Command("lab"))
async def cmd_lab(message: Message) -> None:
    """Отправляет кнопку Mini App для ввода лабораторных тестов."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔬 Открыть форму",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/lab"),
        )]
    ])
    await message.answer(
        "🔬 <b>Ввод лабораторных тестов</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть форму ввода.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
