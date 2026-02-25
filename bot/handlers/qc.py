"""
Хэндлер Инженера ОТК — команда /qc_passport для открытия Mini App.
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

router = Router(name="qc")


@router.message(Command("qc_passport"))
async def cmd_qc_passport(message: Message) -> None:
    """Отправляет кнопку Mini App для заполнения паспорта ОТК."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Открыть форму",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/qc"),
        )]
    ])
    await message.answer(
        "📋 <b>Заполнение паспорта ОТК</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть форму контроля качества.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.message(Command("naming"))
async def cmd_naming(message: Message) -> None:
    """Отправляет кнопку Mini App для присвоения серийных номеров."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏷 Открыть форму",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/qc_naming"),
        )]
    ])
    await message.answer(
        "🏷 <b>Присвоение серийных номеров</b>\n\n"
        "Нажмите кнопку ниже, чтобы присвоить номера трубам.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
