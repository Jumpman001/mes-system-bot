# MES-бот — производство стеклопластиковых труб

Лёгкая MES-система: **Telegram Bot** (управление стадиями производства) +
**Telegram Mini App** (ввод данных сырья, лаборатории и ОТК).

Бизнес-процесс, роли и правила — в [CLAUDE.md](CLAUDE.md).

## Стек

- Python 3.13, [aiogram 3](https://docs.aiogram.dev) (webhook), FastAPI + Jinja2/Tailwind
- PostgreSQL + SQLAlchemy 2.0 (asyncio) + Alembic
- Деплой: Docker → Google Cloud Run (проект `messystembot`, europe-central2)

## Структура

```
app.py            — прод-вход: FastAPI + webhook + Mini App (uvicorn app:app)
bot/
  factory.py      — единая сборка Bot/Dispatcher (общая для webhook и polling)
  main.py         — dev-вход: polling (python -m bot.main)
  auth.py         — проверка ролей в боте, первый админ из ADMIN_IDS
  handlers/       — хэндлеры по ролям
core/
  config.py       — настройки (pydantic-settings, .env)
  workflow.py     — ЕДИНЫЙ источник истины переходов статусов трубы
db/               — модели SQLAlchemy, подключение
web/
  auth.py         — валидация Telegram initData (HMAC) + роли
  routes/         — API и страницы Mini App
  templates/      — HTML (Tailwind)
alembic/          — миграции
tests/            — pytest (workflow, auth)
```

## Переменные окружения (прод — обязательны)

| Переменная | Что это |
|---|---|
| `BOT_TOKEN` | токен бота от @BotFather |
| `WEB_URL` | публичный HTTPS-URL сервиса (Cloud Run) — webhook + Mini App |
| `WEBHOOK_SECRET` | случайная строка (`openssl rand -hex 32`) — защита вебхука |
| `ADMIN_IDS` | Telegram ID корневых админов через запятую (первичная загрузка) |
| `DB_HOST` `DB_PORT` `DB_USER` `DB_PASSWORD` `DB_NAME` | PostgreSQL; `DB_HOST=/cloudsql/...` для Unix-сокета Cloud SQL |
| `TIMEZONE` | таймзона цеха (по умолчанию `Asia/Dushanbe`) |

## Локальная разработка

```bash
# 1. Зависимости
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. PostgreSQL
docker compose up -d

# 3. Миграции
.venv/bin/alembic upgrade head

# 4. Настройки: создать .env (BOT_TOKEN, ADMIN_IDS, WEB_URL...)

# 5а. Только бот (polling, без Mini App):
.venv/bin/python -m bot.main
# 5б. Всё вместе (webhook — нужен публичный HTTPS-туннель в WEB_URL):
.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080
```

## Тесты

```bash
.venv/bin/python -m pytest tests/
```

## Деплой (Cloud Run)

```bash
gcloud builds submit --config cloudbuild.yaml
gcloud run deploy mes-bot \
  --image europe-central2-docker.pkg.dev/messystembot/cloud-run-source-deploy/mes-bot \
  --region europe-central2 \
  --set-env-vars BOT_TOKEN=...,WEB_URL=...,WEBHOOK_SECRET=...,ADMIN_IDS=...,DB_HOST=...,DB_USER=...,DB_PASSWORD=...,DB_NAME=...
# после деплоя — миграции (см. migrate_gcp.sh)
```

Health-check: `GET /healthz` → `{"status": "ok"}`.
