"""
Базовые хэндлеры — /start (авторизация + меню по роли) и диспетчер Reply-кнопок.
"""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from bot.auth import get_effective_role
from bot.keyboards import open_webapp
from db.models import UserRole

# Функции-обработчики из других роутеров (каждая сама проверяет роль)
from bot.handlers.admin import cmd_new_task
from bot.handlers.shift_leader import cmd_work, cmd_receipt
from bot.handlers.dosing import cmd_chemistry
from bot.handlers.technologist import cmd_dry_materials
from bot.handlers.lab import cmd_lab
from bot.handlers.qc import cmd_qc_passport, cmd_naming

router = Router(name="base")

# ── Кнопки меню по ролям ────────────────────────────────────────────────────

BTN_NEW_TASK = "📋 Новая задача"
BTN_REPORTS = "📊 Сводка"
BTN_WORK = "🏭 Управление цехом"
BTN_RECEIPT = "📦 Приход сырья"
BTN_QC = "🛂 Паспорт ОТК"
BTN_NAMING = "🏷 Серийные номера"
BTN_CHEMISTRY = "🧪 Мокрая химия"
BTN_DRY = "🧵 Сухие материалы"
BTN_LAB = "🔬 Лаборатория"
BTN_STOCK = "📦 Склад"
BTN_ABOUT = "ℹ️ О системе"

ROLE_MENUS: dict[UserRole, list[list[str]]] = {
    UserRole.ADMIN: [
        [BTN_NEW_TASK, BTN_REPORTS],
        [BTN_WORK, BTN_STOCK],
    ],
    UserRole.SHIFT_LEADER: [
        [BTN_WORK],
        [BTN_RECEIPT, BTN_STOCK],
    ],
    UserRole.QC_ENGINEER: [
        [BTN_QC],
        [BTN_NAMING],
    ],
    UserRole.DOSING_OPERATOR: [[BTN_CHEMISTRY], [BTN_STOCK]],
    UserRole.TECHNOLOGIST: [[BTN_DRY], [BTN_STOCK]],
    UserRole.LAB_TECHNICIAN: [[BTN_LAB]],
    UserRole.OPERATOR: [[BTN_ABOUT]],
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
    rows = ROLE_MENUS.get(role, [])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b) for b in row] for row in rows],
        resize_keyboard=True,
    )


# ── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Авторизация и главное меню по роли."""
    tg_id = message.from_user.id

    # Роль берём через общий резолвер: он учитывает и ADMIN_IDS
    # (первичная загрузка), и запись в базе.
    role = await get_effective_role(tg_id)

    if role is None:
        await message.answer(
            "⛔ <b>Доступ закрыт</b>\n\n"
            "Вас нет в системе или учётная запись отключена.\n\n"
            f"Ваш Telegram ID: <code>{tg_id}</code>\n"
            "Передайте его руководителю для регистрации.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"👋 <b>КОМПОЗИТ-MES</b>\n\n"
        f"Роль: {ROLE_LABELS.get(role, role.value)}\n\n"
        "Выберите действие в меню ниже.",
        parse_mode="HTML",
        reply_markup=build_keyboard(role),
    )


# ── Диспетчер Reply-кнопок ──────────────────────────────────────────────────
# Кнопки просто вызывают те же функции, что и команды. Проверка прав
# живёт внутри самих функций, поэтому набрать текст кнопки вручную
# в обход своей роли нельзя.

@router.message(F.text == BTN_NEW_TASK)
async def btn_new_task(message: Message, state: FSMContext) -> None:
    # Раньше кнопка лишь просила ввести /new_task вручную — теперь
    # она сразу запускает создание задачи.
    await cmd_new_task(message, state)


@router.message(F.text == BTN_REPORTS)
async def btn_reports(message: Message) -> None:
    await open_webapp(
        message,
        path="/analytics",
        title="📊 Сводка производства",
        description="Показатели выпуска и суммарный расход материалов.",
        button="Открыть сводку",
        roles=(UserRole.ADMIN,),
    )


@router.message(F.text == BTN_WORK)
async def btn_work(message: Message) -> None:
    await cmd_work(message)


@router.message(F.text == BTN_RECEIPT)
async def btn_receipt(message: Message) -> None:
    await cmd_receipt(message)


@router.message(F.text == BTN_QC)
async def btn_qc(message: Message) -> None:
    await cmd_qc_passport(message)


@router.message(F.text == BTN_NAMING)
async def btn_naming(message: Message) -> None:
    await cmd_naming(message)


@router.message(F.text == BTN_CHEMISTRY)
async def btn_chemistry(message: Message) -> None:
    await cmd_chemistry(message)


@router.message(F.text == BTN_DRY)
async def btn_dry_materials(message: Message) -> None:
    await cmd_dry_materials(message)


@router.message(F.text == BTN_LAB)
async def btn_lab(message: Message) -> None:
    await cmd_lab(message)


@router.message(F.text == BTN_STOCK)
async def btn_stock(message: Message) -> None:
    # Импорт здесь, чтобы не было кольцевой зависимости модулей
    from bot.handlers.inventory import cmd_stock
    await cmd_stock(message)


@router.message(F.text == BTN_ABOUT)
async def btn_about(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>КОМПОЗИТ-MES</b>\n\n"
        "Система учёта производства стеклопластиковых труб.\n"
        "Версия 1.0",
        parse_mode="HTML",
    )
