"""
Точка входа FastAPI — Web App (Mini App) для MES-системы.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.routes.receipt import router as receipt_router
from web.routes.dosing import router as dosing_router
from web.routes.technologist import router as technologist_router
from web.routes.lab import router as lab_router
from web.routes.qc import router as qc_router
from web.routes.analytics import router as analytics_router
from web.routes.inventory import router as inventory_router
from web.routes.norms import router as norms_router

# ── Пути ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Создаём папку static, если её нет
STATIC_DIR.mkdir(exist_ok=True)

# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(title="MES Mini App", version="1.0.0")

# Статика и шаблоны
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Роутеры
app.include_router(receipt_router)
app.include_router(dosing_router)
app.include_router(technologist_router)
app.include_router(lab_router)
app.include_router(qc_router)
app.include_router(analytics_router)
app.include_router(inventory_router)
app.include_router(norms_router)
