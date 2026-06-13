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
    Зависимость FastAPI: выдаёт сессию, коммитит при успехе и откатывает
    при любой ошибке. Роутам больше не нужно вручную писать
    try/except + commit — достаточно объявить:

        async def handler(session: AsyncSession = Depends(get_session)):
            session.add(obj)
            # commit произойдёт автоматически

    HTTPException пробрасывается дальше (откат безвреден — коммитить нечего).
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
