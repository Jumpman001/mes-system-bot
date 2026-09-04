"""
Единая точка входа: FastAPI + aiogram webhook + Mini App.
Запуск: uvicorn app:app --host 0.0.0.0 --port 8080

Bot и Dispatcher собираются в bot/factory.py — общем с polling-режимом
(bot/main.py), чтобы сборки не расходились.
"""

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram.types import Update
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from bot.factory import create_bot, create_dispatcher, setup_bot_commands
from core.config import settings
from web.errors import register_exception_handlers

# ── Роутеры Mini App ─────────────────────────────────────────────────────────
from web.routes.receipt import router as receipt_web
from web.routes.dosing import router as dosing_web
from web.routes.technologist import router as technologist_web
from web.routes.lab import router as lab_web
from web.routes.qc import router as qc_web
from web.routes.analytics import router as analytics_web
from web.routes.inventory import router as inventory_web
from web.routes.norms import router as norms_web
from web.routes.corrections import router as corrections_web

# ── Логирование ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Bot + Dispatcher (из общей фабрики) ──────────────────────────────────────
WEBHOOK_PATH = "/webhook"

bot = create_bot()
dp = create_dispatcher()


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
    # Обновляем синюю кнопку меню (best-effort — не валим старт при сбое)
    try:
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning("⚠️ Не удалось установить меню команд: %s", e)
    yield
    # Вебхук при остановке контейнера Cloud Run не удаляем
    await bot.session.close()
    logger.info("🛑 Сессия закрыта.")


# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(title="MES Bot + Mini App", version="1.0.0", lifespan=lifespan)

# Единые обработчики ошибок БД / непредвиденных исключений
register_exception_handlers(app)


# Health-check (для мониторинга и readiness-проб)
@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


# Webhook endpoint
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    # Проверяем секрет: Telegram присылает его в заголовке при каждом апдейте.
    # Без этого любой, кто знает URL, мог бы слать боту поддельные апдейты.
    if settings.WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not secret or not hmac.compare_digest(secret, settings.WEBHOOK_SECRET):
            logger.warning("Webhook: неверный или отсутствующий secret token.")
            return Response(status_code=403)

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return Response(status_code=200)


# Mini App роутеры
for r in [receipt_web, dosing_web, technologist_web, lab_web,
          qc_web, analytics_web, inventory_web, norms_web, corrections_web]:
    app.include_router(r)

# Статика
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
