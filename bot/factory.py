"""
Фабрика бота — ЕДИНОЕ место сборки Bot и Dispatcher.

Раньше бот собирался дважды (app.py для webhook и bot/main.py для polling),
и сборки разъехались: polling не подключал report_router, а webhook не
устанавливал меню команд. Теперь обе точки входа используют эту фабрику.
"""

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent

from core.config import settings
from core.exceptions import MesBotError

from bot.handlers.base import router as base_router
from bot.handlers.users_admin import router as users_admin_router
from bot.handlers.admin import router as admin_router
from bot.handlers.shift_leader import router as shift_leader_router
from bot.handlers.dosing import router as dosing_router
from bot.handlers.technologist import router as technologist_router
from bot.handlers.lab import router as lab_router
from bot.handlers.qc import router as qc_router
from bot.handlers.report import router as report_router
from bot.handlers.inventory import router as inventory_router
from bot.handlers.corrections import router as corrections_router

logger = logging.getLogger(__name__)

# base ПЕРВЫМ — в нём /start и диспетчер Reply-кнопок
ALL_ROUTERS = [
    base_router,
    users_admin_router,
    admin_router,
    shift_leader_router,
    dosing_router,
    technologist_router,
    lab_router,
    qc_router,
    report_router,
    inventory_router,
    corrections_router,
]

# Синяя кнопка меню Telegram. Здесь только реально существующие команды.
BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню и обновление клавиатуры"),
    BotCommand(command="work", description="🏭 Управление цехом (Нач. смены)"),
    BotCommand(command="receipt", description="📦 Приход сырья (Нач. смены)"),
    BotCommand(command="chemistry", description="🧪 Мокрая химия (Дозировщик)"),
    BotCommand(command="dry_materials", description="🧵 Сухие материалы (Технолог)"),
    BotCommand(command="lab", description="🔬 Тесты (Лаборант)"),
    BotCommand(command="qc_passport", description="🛂 Паспорт качества (ОТК)"),
    BotCommand(command="naming", description="🏷 Присвоение номеров (ОТК)"),
    BotCommand(command="new_task", description="📋 Новая задача (Админ)"),
    BotCommand(command="pipe_report", description="📑 Досье на трубу"),
    BotCommand(command="stock", description="📦 Остатки склада"),
    BotCommand(command="my_entries", description="✏️ Мои записи и исправления"),
    BotCommand(command="corrections", description="✅ Заявки на исправление (Админ)"),
]


def create_bot() -> Bot:
    """Создаёт Bot с HTML-разметкой по умолчанию."""
    return Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Создаёт Dispatcher со всеми роутерами и глобальным обработчиком ошибок."""
    dp = Dispatcher()
    for r in ALL_ROUTERS:
        dp.include_router(r)

    @dp.errors()
    async def global_error_handler(event: ErrorEvent):
        exception = event.exception
        logger.exception(
            "Unhandled exception for Update %s: %s",
            event.update.update_id, exception,
        )
        if isinstance(exception, MesBotError):
            user_msg = f"⚠️ Ошибка: {exception}"
        else:
            user_msg = "⚠️ Произошла непредвиденная ошибка. Обратитесь к администратору."
        if event.update.message:
            await event.update.message.answer(user_msg)
        elif event.update.callback_query:
            if event.update.callback_query.message:
                await event.update.callback_query.message.answer(user_msg)
            await event.update.callback_query.answer()

    return dp


async def setup_bot_commands(bot: Bot) -> None:
    """Устанавливает список команд для синей кнопки меню Telegram."""
    await bot.set_my_commands(BOT_COMMANDS)
    logger.info("Меню команд установлено (%d команд)", len(BOT_COMMANDS))
