"""
Отправка уведомлений администраторам из веб-части.

Веб-роуты не держат объект бота (он живёт в app.py), поэтому здесь
создаётся короткоживущая сессия только на время отправки. Сообщений
мало — заявки на исправление подают редко, так что это дёшево.
"""

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import User, UserRole

logger = logging.getLogger(__name__)


async def admin_ids(session: AsyncSession) -> list[int]:
    """Все администраторы: из настройки ADMIN_IDS и из базы."""
    ids = set(settings.admin_ids)
    rows = (
        await session.execute(
            select(User.telegram_id).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        )
    ).scalars().all()
    ids.update(rows)
    return sorted(ids)


async def notify_correction_request(
    session: AsyncSession,
    *,
    request_id: int,
    author_name: str,
    title: str,
    field_label: str,
    old_value: str | None,
    new_value: str | None,
    reason: str,
) -> None:
    """
    Сообщает администраторам о новой заявке на исправление
    и даёт кнопки «Одобрить» / «Отклонить».

    Ошибку отправки не пробрасываем: заявка уже сохранена, и работник
    не должен видеть сбой из-за проблем с Telegram.
    """
    if not settings.BOT_TOKEN:
        logger.warning("BOT_TOKEN не задан — уведомление не отправлено.")
        return

    targets = await admin_ids(session)
    if not targets:
        logger.warning("Нет администраторов для уведомления о заявке #%s", request_id)
        return

    text = (
        f"✏️ <b>Заявка на исправление #{request_id}</b>\n\n"
        f"От: {author_name}\n"
        f"Запись: {title}\n"
        f"Поле: {field_label}\n\n"
        f"Было: <b>{old_value if old_value is not None else '—'}</b>\n"
        f"Станет: <b>{new_value if new_value is not None else '—'}</b>\n\n"
        f"Причина: <i>{reason}</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"corr_ok:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"corr_no:{request_id}"),
    ]])

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        for admin in targets:
            try:
                await bot.send_message(admin, text, reply_markup=keyboard)
            except Exception as e:
                logger.warning("Не удалось уведомить админа %s: %s", admin, e)
    finally:
        await bot.session.close()


async def notify_user(session: AsyncSession, telegram_id: int, text: str) -> None:
    """Сообщает работнику решение по его заявке."""
    if not settings.BOT_TOKEN:
        return
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        await bot.send_message(telegram_id, text)
    except Exception as e:
        logger.warning("Не удалось уведомить работника %s: %s", telegram_id, e)
    finally:
        await bot.session.close()
