"""
Авторизация на стороне бота (aiogram).

Раньше «админские» команды (/add_user, /new_task и т.п.) НЕ проверяли роль —
любой пользователь Telegram мог, например, сделать себя администратором через
/add_user. Теперь роль проверяется централизованно здесь.

Первичная загрузка: первый администратор берётся не из БД (её ещё некому
заполнить), а из настройки ADMIN_IDS (env-переменная). Эти ID всегда считаются
администраторами.
"""

import logging

from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from core.config import settings
from db.database import async_session
from db.models import User, UserRole

logger = logging.getLogger(__name__)


def is_role_allowed(role: UserRole | None, required: tuple[UserRole, ...]) -> bool:
    """Чистая проверка: подходит ли роль (админ допускается всегда)."""
    if role is None:
        return False
    return role in (set(required) | {UserRole.ADMIN})


async def get_effective_role(telegram_id: int) -> UserRole | None:
    """
    Эффективная роль пользователя:
    - если ID в ADMIN_IDS — всегда ADMIN (первичная загрузка);
    - иначе роль активного пользователя из БД;
    - None, если пользователь не найден/деактивирован.
    """
    if telegram_id in settings.admin_ids:
        return UserRole.ADMIN

    async with async_session() as session:
        user = (
            await session.execute(
                select(User).where(
                    User.telegram_id == telegram_id,
                    User.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    return user.role if user else None


async def ensure_message_role(message: Message, *roles: UserRole) -> bool:
    """
    Проверяет роль отправителя сообщения. При нехватке прав отвечает отказом
    и возвращает False — вызывающий хэндлер должен прекратить работу.
    """
    role = await get_effective_role(message.from_user.id)
    if not is_role_allowed(role, roles):
        await message.answer("⛔ Недостаточно прав для этой команды.")
        return False
    return True


async def ensure_registered(message: Message) -> bool:
    """
    Любой активный зарегистрированный пользователь (роль не важна).
    Для команд «на чтение» вроде /stock и /pipe_report — данные производства
    не должны быть видны случайным людям, написавшим боту.
    """
    role = await get_effective_role(message.from_user.id)
    if role is None:
        await message.answer(
            "⛔ Вы не зарегистрированы в системе.\n"
            "Передайте ваш Telegram ID руководителю для регистрации."
        )
        return False
    return True


async def ensure_callback_role(callback: CallbackQuery, *roles: UserRole) -> bool:
    """То же для callback-кнопок (показывает alert и возвращает False)."""
    role = await get_effective_role(callback.from_user.id)
    if not is_role_allowed(role, roles):
        await callback.answer("⛔ Недостаточно прав.", show_alert=True)
        return False
    return True
