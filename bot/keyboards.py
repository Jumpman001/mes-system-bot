"""
Открытие экранов Mini App из бота.

Раньше четыре хэндлера (химия, сухие материалы, лаборатория, ОТК) были
почти дословными копиями друг друга и не проверяли роль. Теперь общий
помощник: проверка роли, проверка настройки WEB_URL и сама кнопка.
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from bot.auth import ensure_message_role
from core.config import settings
from db.models import UserRole


async def open_webapp(
    message: Message,
    *,
    path: str,
    title: str,
    description: str,
    button: str,
    roles: tuple[UserRole, ...],
) -> None:
    """
    Отправляет кнопку открытия экрана Mini App.

    path — путь внутри приложения, например "/dosing".
    roles — кому можно (администратор допускается всегда).
    """
    if not await ensure_message_role(message, *roles):
        return

    # Без WEB_URL Telegram отклонит кнопку: подскажем причину вместо
    # молчаливой ошибки «кнопка не работает».
    if not settings.WEB_URL:
        await message.answer(
            "⚠️ <b>Веб-формы не настроены</b>\n\n"
            "Администратору: задайте переменную <code>WEB_URL</code> "
            "(публичный адрес сервиса) и перезапустите бота.",
            parse_mode="HTML",
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=button,
            web_app=WebAppInfo(url=f"{settings.WEB_URL.rstrip('/')}{path}"),
        )
    ]])
    await message.answer(
        f"<b>{title}</b>\n\n{description}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
