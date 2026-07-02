"""
Точка входа Telegram-бота в режиме polling (локальная разработка).
Прод работает через webhook — см. app.py. Сборка бота общая: bot/factory.py.

Запуск: python -m bot.main
"""

import asyncio
import logging

from bot.factory import create_bot, create_dispatcher, setup_bot_commands

# ── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Запуск бота (polling)."""
    bot = create_bot()
    dp = create_dispatcher()

    await setup_bot_commands(bot)

    logger.info("Бот запущен. Polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
