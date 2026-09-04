"""
Хэндлеры администратора — заявки на исправление данных.

/corrections — список заявок, ждущих решения.
Кнопки «Одобрить» / «Отклонить» приходят и в уведомлении о новой заявке.

Данные меняются ТОЛЬКО здесь: работник сам исправить запись не может.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from bot.auth import ensure_callback_role, ensure_message_role
from core.utils import format_local_time
from db.database import async_session
from db.models import CorrectionRequest, CorrectionStatus, User, UserRole
from web.services.correction_service import apply_correction, reject_correction

router = Router(name="corrections")
logger = logging.getLogger(__name__)


def _decision_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"corr_ok:{request_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"corr_no:{request_id}"),
    ]])


async def _author_name(session, telegram_id: int) -> str:
    """Имя заявителя, если он есть в базе."""
    user = (
        await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
    ).scalar_one_or_none()
    return user.full_name if user else f"ID {telegram_id}"


def _describe(req: CorrectionRequest, author: str) -> str:
    return (
        f"✏️ <b>Заявка #{req.id}</b>\n"
        f"От: {author}\n"
        f"Запись: {req.target.value} #{req.record_id}\n"
        f"Поле: <code>{req.field_name}</code>\n\n"
        f"Было: <b>{req.old_value or '—'}</b>\n"
        f"Станет: <b>{req.new_value or '—'}</b>\n\n"
        f"Причина: <i>{req.reason}</i>\n"
        f"Подана: {format_local_time(req.requested_at)}"
    )


@router.message(Command("corrections"))
async def cmd_corrections(message: Message) -> None:
    """Показывает заявки, ожидающие решения администратора."""
    if not await ensure_message_role(message, UserRole.ADMIN):
        return

    async with async_session() as session:
        pending = (
            await session.execute(
                select(CorrectionRequest)
                .where(CorrectionRequest.status == CorrectionStatus.PENDING)
                .order_by(CorrectionRequest.id)
            )
        ).scalars().all()

        if not pending:
            await message.answer("✅ Заявок на исправление нет.")
            return

        await message.answer(
            f"✏️ <b>Заявок на рассмотрении: {len(pending)}</b>",
            parse_mode="HTML",
        )
        for req in pending:
            author = await _author_name(session, req.requested_by)
            await message.answer(
                _describe(req, author),
                parse_mode="HTML",
                reply_markup=_decision_keyboard(req.id),
            )


async def _load_pending(session, request_id: int) -> CorrectionRequest | None:
    """Берёт заявку, только если она ещё не рассмотрена."""
    req = (
        await session.execute(
            select(CorrectionRequest).where(CorrectionRequest.id == request_id)
        )
    ).scalar_one_or_none()
    if req is None or req.status != CorrectionStatus.PENDING:
        return None
    return req


@router.callback_query(F.data.startswith("corr_ok:"))
async def approve(callback: CallbackQuery) -> None:
    """Одобрить исправление: применить и пересчитать склад."""
    if not await ensure_callback_role(callback, UserRole.ADMIN):
        return

    request_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        req = await _load_pending(session, request_id)
        if req is None:
            await callback.answer("Заявка уже рассмотрена.", show_alert=True)
            return

        try:
            await apply_correction(session, req, callback.from_user.id)
            await session.commit()
        except ValueError as e:
            await session.rollback()
            await callback.answer(str(e), show_alert=True)
            return

        author = req.requested_by
        field, old, new = req.field_name, req.old_value, req.new_value

    await callback.answer("Исправление применено.")
    await callback.message.edit_text(
        f"✅ <b>Заявка #{request_id} одобрена</b>\n\n"
        f"Поле <code>{field}</code>: {old or '—'} → <b>{new or '—'}</b>\n"
        "Склад пересчитан на разницу.",
        parse_mode="HTML",
    )

    # Сообщаем работнику
    from bot.notify import notify_user
    async with async_session() as session:
        await notify_user(
            session, author,
            f"✅ Ваша заявка #{request_id} одобрена.\n"
            f"Значение исправлено: {old or '—'} → <b>{new or '—'}</b>",
        )


@router.callback_query(F.data.startswith("corr_no:"))
async def reject(callback: CallbackQuery) -> None:
    """Отклонить исправление: данные остаются как были."""
    if not await ensure_callback_role(callback, UserRole.ADMIN):
        return

    request_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        req = await _load_pending(session, request_id)
        if req is None:
            await callback.answer("Заявка уже рассмотрена.", show_alert=True)
            return

        await reject_correction(session, req, callback.from_user.id)
        await session.commit()
        author = req.requested_by

    await callback.answer("Заявка отклонена.")
    await callback.message.edit_text(
        f"❌ <b>Заявка #{request_id} отклонена</b>\n\nДанные остались без изменений.",
        parse_mode="HTML",
    )

    from bot.notify import notify_user
    async with async_session() as session:
        await notify_user(
            session, author,
            f"❌ Ваша заявка #{request_id} отклонена администратором.\n"
            "Данные остались прежними. Уточните у руководителя.",
        )


@router.message(Command("my_entries"))
async def cmd_my_entries(message: Message) -> None:
    """Открывает экран «мои записи» — оттуда подаётся заявка на исправление."""
    from bot.keyboards import open_webapp

    await open_webapp(
        message,
        path="/my_entries",
        title="✏️ Мои записи",
        description=(
            "Здесь видно всё, что вы внесли. Если ошиблись — нажмите "
            "«Исправить»: заявка уйдёт администратору на согласование."
        ),
        button="Открыть мои записи",
        # Доступно всем ролям, кто вносит данные
        roles=(
            UserRole.DOSING_OPERATOR,
            UserRole.TECHNOLOGIST,
            UserRole.LAB_TECHNICIAN,
            UserRole.QC_ENGINEER,
            UserRole.SHIFT_LEADER,
        ),
    )
