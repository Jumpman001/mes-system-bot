"""
Точка входа Telegram-бота.
Инициализация Bot, Dispatcher, подключение роутеров, запуск polling.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from core.config import settings
from bot.handlers.base import router as base_router
from bot.handlers.users_admin import router as users_admin_router
from bot.handlers.admin import router as admin_router
from bot.handlers.shift_leader import router as shift_leader_router
from bot.handlers.dosing import router as dosing_router
from bot.handlers.technologist import router as technologist_router
from bot.handlers.lab import router as lab_router
from bot.handlers.qc import router as qc_router
from bot.handlers.report import router as report_router
from bot.handlers.ai_assistant import router as ai_assistant_router
from bot.handlers.inventory import router as inventory_router

# ── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    """Устанавливает список команд для синей кнопки меню Telegram."""
    commands = [
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
        BotCommand(command="ask", description="🤖 Задать вопрос по документации"),
        BotCommand(command="stock", description="📦 Остатки склада"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Меню команд установлено (%d команд)", len(commands))


async def main() -> None:
    """Запуск бота."""
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Подключаем роутеры (base ПЕРВЫМ для /start)
    dp.include_router(base_router)
    dp.include_router(users_admin_router)
    dp.include_router(admin_router)
    dp.include_router(shift_leader_router)
    dp.include_router(dosing_router)
    dp.include_router(technologist_router)
    dp.include_router(lab_router)
    dp.include_router(qc_router)
    dp.include_router(report_router)
    dp.include_router(ai_assistant_router)
    dp.include_router(inventory_router)

    # Устанавливаем меню команд
    await set_bot_commands(bot)

    logger.info("Бот запущен. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
