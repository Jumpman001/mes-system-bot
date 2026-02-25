"""
Базовые хэндлеры — /start (авторизация + главное меню) и диспетчер Reply-кнопок.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select

from db.database import async_session
from db.models import User, UserRole

# Импорт функций-обработчиков из других роутеров
from bot.handlers.admin import cmd_new_task
from bot.handlers.shift_leader import cmd_work, cmd_receipt
from bot.handlers.dosing import cmd_chemistry
from bot.handlers.technologist import cmd_dry_materials
from bot.handlers.lab import cmd_lab
from bot.handlers.qc import cmd_qc_passport

router = Router(name="base")

# ── Карта: роль → кнопки ────────────────────────────────────────────────────

ROLE_MENUS: dict[UserRole, list[list[str]]] = {
    UserRole.ADMIN: [
        ["📋 Новая задача"],
        ["📊 Отчеты"],
    ],
    UserRole.SHIFT_LEADER: [
        ["🏭 Управление цехом"],
        ["📦 Приход сырья"],
    ],
    UserRole.QC_ENGINEER: [
        ["🛂 Паспорта ОТК"],
    ],
    UserRole.DOSING_OPERATOR: [
        ["🧪 Мокрая химия"],
    ],
    UserRole.TECHNOLOGIST: [
        ["🧵 Сухие материалы"],
    ],
    UserRole.LAB_TECHNICIAN: [
        ["🔬 Лаборатория"],
    ],
    UserRole.OPERATOR: [
        ["ℹ️ О системе"],
    ],
}

ROLE_LABELS: dict[UserRole, str] = {
    UserRole.ADMIN: "👑 Администратор",
    UserRole.QC_ENGINEER: "🛂 Инженер ОТК",
    UserRole.SHIFT_LEADER: "🏭 Начальник смены",
    UserRole.DOSING_OPERATOR: "🧪 Дозировщик",
    UserRole.LAB_TECHNICIAN: "🔬 Лаборант",
    UserRole.TECHNOLOGIST: "🧵 Технолог",
    UserRole.OPERATOR: "👷 Оператор",
}


def build_keyboard(role: UserRole) -> ReplyKeyboardMarkup:
    """Строит Reply-клавиатуру по роли пользователя."""
    buttons = ROLE_MENUS.get(role, [])
    keyboard = [[KeyboardButton(text=btn) for btn in row] for row in buttons]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Авторизация + главное меню по роли."""
    tg_id = message.from_user.id

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "⛔ <b>Доступ запрещён</b>\n\n"
            "Вы не зарегистрированы в системе.\n"
            f"Ваш Telegram ID: <code>{tg_id}</code>\n\n"
            "Передайте его руководителю для регистрации.",
            parse_mode="HTML",
        )
        return

    if not user.is_active:
        await message.answer(
            "⛔ <b>Ваш аккаунт деактивирован.</b>\n\n"
            "Обратитесь к руководству.",
            parse_mode="HTML",
        )
        return

    label = ROLE_LABELS.get(user.role, str(user.role.value))
    kb = build_keyboard(user.role)

    await message.answer(
        f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
        f"Роль: {label}\n\n"
        "Выберите действие из меню ниже ⬇️",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ── Диспетчер Reply-кнопок ──────────────────────────────────────────────────

@router.message(F.text == "📋 Новая задача")
async def btn_new_task(message: Message) -> None:
    from aiogram.fsm.context import FSMContext
    # Для FSM нужен state, но при нажатии Reply-кнопки его нет в аргументах.
    # Поэтому просто отправляем команду /new_task
    await message.answer(
        "📋 Для создания новой задачи используйте команду:\n"
        "<code>/new_task</code>",
        parse_mode="HTML",
    )


@router.message(F.text == "📊 Отчеты")
async def btn_reports(message: Message) -> None:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
    from core.config import settings
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📈 Открыть дашборд",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/analytics"),
        )]
    ])
    await message.answer(
        "📈 <b>Оперативная сводка производства</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть дашборд.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.message(F.text == "🏭 Управление цехом")
async def btn_work(message: Message) -> None:
    await cmd_work(message)


@router.message(F.text == "📦 Приход сырья")
async def btn_receipt(message: Message) -> None:
    await cmd_receipt(message)


@router.message(F.text == "🛂 Паспорта ОТК")
async def btn_qc(message: Message) -> None:
    await cmd_qc_passport(message)


@router.message(F.text == "🧪 Мокрая химия")
async def btn_chemistry(message: Message) -> None:
    await cmd_chemistry(message)


@router.message(F.text == "🧵 Сухие материалы")
async def btn_dry_materials(message: Message) -> None:
    await cmd_dry_materials(message)


@router.message(F.text == "🔬 Лаборатория")
async def btn_lab(message: Message) -> None:
    await cmd_lab(message)


@router.message(F.text == "ℹ️ О системе")
async def btn_about(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>КОМПОЗИТ-MES</b>\n\n"
        "Система управления производством GRP-труб.\n"
        "Версия: 1.0.0",
        parse_mode="HTML",
    )
