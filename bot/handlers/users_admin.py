"""
Управление пользователями — /add_user и /remove_user (только для админов).
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from db.database import async_session
from db.models import User, UserRole

router = Router(name="users_admin")

VALID_ROLES = {r.value for r in UserRole}

ROLE_LABELS = {
    "admin": "👑 Администратор",
    "qc_engineer": "🛂 Инженер ОТК",
    "shift_leader": "🏭 Начальник смены",
    "dosing_operator": "🧪 Дозировщик",
    "lab_technician": "🔬 Лаборант",
    "technologist": "🧵 Технолог",
    "operator": "👷 Оператор",
}


@router.message(Command("add_user"))
async def cmd_add_user(message: Message) -> None:
    """
    /add_user <telegram_id> <role> <ФИО>
    Если пользователь деактивирован — реактивирует и обновляет роль.
    TODO: ограничить доступ — разрешить только пользователям с ролью admin.
    """
    args = message.text.split(maxsplit=3)

    if len(args) < 4:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/add_user &lt;telegram_id&gt; &lt;role&gt; &lt;ФИО&gt;</code>\n\n"
            "Пример:\n"
            "<code>/add_user 123456789 shift_leader Иванов Иван</code>\n\n"
            f"Доступные роли:\n<code>{', '.join(sorted(VALID_ROLES))}</code>",
            parse_mode="HTML",
        )
        return

    _, tg_id_str, role_str, full_name = args

    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await message.answer("❌ <b>telegram_id</b> должен быть числом.", parse_mode="HTML")
        return

    if role_str not in VALID_ROLES:
        await message.answer(
            f"❌ Неизвестная роль: <code>{role_str}</code>\n\n"
            f"Доступные: <code>{', '.join(sorted(VALID_ROLES))}</code>",
            parse_mode="HTML",
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if existing.is_active:
                await message.answer(
                    f"⚠️ Пользователь <code>{tg_id}</code> уже активен.",
                    parse_mode="HTML",
                )
                return
            # Реактивация деактивированного пользователя
            existing.is_active = True
            existing.role = UserRole(role_str)
            existing.full_name = full_name
            await session.commit()
            await message.answer(
                f"🔄 <b>Пользователь реактивирован</b>\n\n"
                f"👤 {full_name}\n"
                f"🆔 <code>{tg_id}</code>\n"
                f"🎭 {ROLE_LABELS.get(role_str, role_str)}",
                parse_mode="HTML",
            )
            return

        user = User(
            telegram_id=tg_id,
            full_name=full_name,
            role=UserRole(role_str),
        )
        session.add(user)
        await session.commit()

    await message.answer(
        f"✅ <b>Пользователь добавлен</b>\n\n"
        f"👤 {full_name}\n"
        f"🆔 <code>{tg_id}</code>\n"
        f"🎭 {ROLE_LABELS.get(role_str, role_str)}",
        parse_mode="HTML",
    )


@router.message(Command("remove_user"))
async def cmd_remove_user(message: Message) -> None:
    """
    /remove_user <telegram_id>
    Деактивирует пользователя (is_active = False).
    TODO: ограничить доступ — разрешить только пользователям с ролью admin.
    """
    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Использование:\n"
            "<code>/remove_user &lt;telegram_id&gt;</code>",
            parse_mode="HTML",
        )
        return

    try:
        tg_id = int(args[1])
    except ValueError:
        await message.answer("❌ <b>telegram_id</b> должен быть числом.", parse_mode="HTML")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{tg_id}</code> не найден.",
                parse_mode="HTML",
            )
            return

        if not user.is_active:
            await message.answer(
                f"ℹ️ Пользователь <b>{user.full_name}</b> уже деактивирован.",
                parse_mode="HTML",
            )
            return

        user.is_active = False
        await session.commit()

    await message.answer(
        f"✅ Доступ для пользователя <b>{user.full_name}</b> закрыт.\n\n"
        f"🆔 <code>{tg_id}</code>",
        parse_mode="HTML",
    )
