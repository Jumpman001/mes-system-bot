"""
Alembic env.py — асинхронный режим.
Импортирует ВСЕ модели через db.models и подтягивает DATABASE_URL из core.config.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Конфигурация Alembic ─────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Импорт ВСЕХ моделей для autogenerate ─────────────────────────────────
# Импортируем Base — она содержит metadata всех моделей,
# зарегистрированных через наследование (User, Task, Pipe, …).
from db.models import Base  # noqa: E402

target_metadata = Base.metadata

# ── Подмена URL из Settings (вместо alembic.ini) ─────────────────────────
from core.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


# ── Offline-миграции (без подключения к БД) ──────────────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online-миграции (асинхронные) ────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
