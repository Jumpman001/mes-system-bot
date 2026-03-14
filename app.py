"""
Единая точка входа: FastAPI + aiogram webhook + Mini App.
Запуск: uvicorn app:app --host 0.0.0.0 --port 8080
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent, Update
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.exceptions import MesBotError

# ── Роутеры бота ─────────────────────────────────────────────────────────────
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

# ── Роутеры Mini App ─────────────────────────────────────────────────────────
from web.routes.receipt import router as receipt_web
from web.routes.dosing import router as dosing_web
from web.routes.technologist import router as technologist_web
from web.routes.lab import router as lab_web
from web.routes.qc import router as qc_web
from web.routes.analytics import router as analytics_web
from web.routes.inventory import router as inventory_web
from web.routes.norms import router as norms_web

# ── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Bot + Dispatcher ─────────────────────────────────────────────────────────
WEBHOOK_PATH = "/webhook"

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Подключаем роутеры бота
for r in [base_router, users_admin_router, admin_router,
          shift_leader_router, dosing_router, technologist_router,
          lab_router, qc_router, report_router,
          inventory_router]:
    dp.include_router(r)


# Глобальный обработчик ошибок
@dp.errors()
async def global_error_handler(event: ErrorEvent):
    exception = event.exception
    logger.exception("Unhandled exception for Update %s: %s",
                     event.update.update_id, exception)
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


# ── Lifespan: webhook setup / teardown ───────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI):
    webhook_url = settings.WEB_URL.rstrip("/") + WEBHOOK_PATH
    try:
        await bot.set_webhook(
            webhook_url,
            secret_token=settings.WEBHOOK_SECRET or None,
        )
        logger.info("✅ Webhook установлен → %s", webhook_url)
    except Exception as e:
        logger.warning("⚠️ Не удалось установить webhook (%s). "
                       "Обновите WEB_URL и передеплойте.", e)
    yield
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    await bot.session.close()
    logger.info("🛑 Сессия закрыта.")


# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(title="MES Bot + Mini App", version="1.0.0", lifespan=lifespan)


# Webhook endpoint
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return Response(status_code=200)


# Mini App роутеры
for r in [receipt_web, dosing_web, technologist_web, lab_web,
          qc_web, analytics_web, inventory_web, norms_web]:
    app.include_router(r)

# Статика
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
