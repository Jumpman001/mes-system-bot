# Webhook Migration + Cloud Run Deployment

**Goal:** Переключить бота с polling на webhooks и развернуть единое приложение (бот + Mini App) в Google Cloud Run Service.

**Architecture:** Объединить `bot/main.py` и `web/main.py` в один FastAPI-сервер. Telegram будет отправлять обновления на `POST /webhook`, а Mini App продолжит работать на тех же маршрутах. Cloud Run даст публичный HTTPS URL.

**Tech Stack:** Python 3.13, aiogram 3.x (webhook mode), FastAPI, Cloud Run, Cloud SQL (PostgreSQL), Artifact Registry.

---

### Task 1: Добавить WEBHOOK_PATH в конфигурацию

**Files:**
- Modify: `core/config.py`

**Step 1:** Добавить поля в `Settings`:

```python
# ── Webhook ──────────────────────────────────────────────────────────
WEBHOOK_SECRET: str = ""       # секрет для проверки запросов от Telegram
PORT: int = 8080               # Cloud Run использует $PORT (обычно 8080)
```

---

### Task 2: Создать единую точку входа (webhook + web)

**Files:**
- Create: `app.py` (корень проекта)

**Step 1:** Создать `app.py` — единый FastAPI-сервер:

```python
"""
Единая точка входа: FastAPI + aiogram webhook.
Запускается через uvicorn.
"""
import logging, os
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from fastapi import FastAPI, Request, Response

from core.config import settings
from core.exceptions import MesBotError

# Импортируем все роутеры бота
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

# Импортируем веб-роутеры (Mini App)
from web.main import app as mini_app_router  # переиспользуем роутеры

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"

bot = Bot(token=settings.BOT_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Подключаем роутеры бота
for r in [base_router, users_admin_router, admin_router,
          shift_leader_router, dosing_router, technologist_router,
          lab_router, qc_router, report_router,
          ai_assistant_router, inventory_router]:
    dp.include_router(r)

# Глобальный обработчик ошибок (из bot/main.py)
from aiogram.types import ErrorEvent
@dp.errors()
async def global_error_handler(event: ErrorEvent):
    logger.exception("Unhandled: %s", event.exception)
    msg = (f"⚠️ {event.exception}" if isinstance(event.exception, MesBotError)
           else "⚠️ Внутренняя ошибка. Обратитесь к администратору.")
    if event.update.message:
        await event.update.message.answer(msg)
    elif event.update.callback_query:
        if event.update.callback_query.message:
            await event.update.callback_query.message.answer(msg)
        await event.update.callback_query.answer()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup: устанавливаем webhook
    webhook_url = settings.WEB_URL.rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(webhook_url, secret_token=settings.WEBHOOK_SECRET or None)
    logger.info("Webhook set → %s", webhook_url)
    yield
    # Shutdown: удаляем webhook
    await bot.delete_webhook()
    await bot.session.close()


app = FastAPI(title="MES Bot + Mini App", lifespan=lifespan)

# Webhook endpoint
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return Response(status_code=200)

# Подключаем Mini App роутеры
from web.routes.receipt import router as receipt_router_web
from web.routes.dosing import router as dosing_router_web
from web.routes.technologist import router as technologist_router_web
from web.routes.lab import router as lab_router_web
from web.routes.qc import router as qc_router_web
from web.routes.analytics import router as analytics_router_web
from web.routes.inventory import router as inventory_router_web
from web.routes.norms import router as norms_router_web

for r in [receipt_router_web, dosing_router_web, technologist_router_web,
          lab_router_web, qc_router_web, analytics_router_web,
          inventory_router_web, norms_router_web]:
    app.include_router(r)

# Статика
from pathlib import Path
from fastapi.staticfiles import StaticFiles
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
```

---

### Task 3: Обновить Dockerfile

**Files:**
- Modify: `Dockerfile`

**Step 1:** Изменить `CMD` для запуска через uvicorn:

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt
COPY . .
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

### Task 4: Добавить uvicorn в зависимости

**Files:**
- Modify: `requirements-prod.txt`

**Step 1:** Добавить `uvicorn[standard]` если не установлено.

---

### Task 5: Собрать Docker-образ и развернуть в Cloud Run

**Step 1:** Собрать образ через Cloud Build:

```bash
gcloud builds submit --tag us-central1-docker.pkg.dev/messystembot/cloud-run-source-deploy/mes-bot:latest
```

**Step 2:** Развернуть Cloud Run Service:

```bash
gcloud run deploy mes-bot \
  --image us-central1-docker.pkg.dev/messystembot/cloud-run-source-deploy/mes-bot:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "BOT_TOKEN=<token>,DB_HOST=<cloud-sql-ip>,DB_PORT=5432,DB_USER=mes_user,DB_PASSWORD=<pwd>,DB_NAME=mes_db,WEB_URL=<cloud-run-url>,GEMINI_API_KEY=<key>" \
  --add-cloudsql-instances messystembot:us-central1:mes-postgres-db
```

**Step 3:** Обновить `WEB_URL` на URL, выданный Cloud Run, и повторить деплой.

---

### Task 6: Верификация

- Открыть URL Cloud Run в браузере → Mini App должна загрузиться
- Отправить `/start` боту в Telegram → бот должен ответить
- Проверить логи: `gcloud run services logs read mes-bot --region us-central1`
