"""
Хэндлер Дозировщика — команда /chemistry для открытия Mini App.
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

router = Router(name="dosing")


@router.message(Command("chemistry"))
async def cmd_chemistry(message: Message) -> None:
    """Отправляет кнопку Mini App для ввода расхода химии."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🧪 Открыть форму",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/dosing"),
        )]
    ])
    await message.answer(
        "🧪 <b>Ввод фактического расхода химии</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть форму ввода.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
