"""
Асинхронное подключение к PostgreSQL.
Engine + SessionFactory + get_session() для инъекции зависимостей.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings

# ── Async Engine ─────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

# ── Фабрика сессий ──────────────────────────────────────────────────────────
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Генератор сессий (для DI) ───────────────────────────────────────────────
async def get_session() -> AsyncSession:
    """
    Возвращает асинхронную сессию.
    Использование:
        async with get_session() as session:
            ...
    """
    async with async_session() as session:
        yield session
