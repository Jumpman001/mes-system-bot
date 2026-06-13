"""
Конфигурация приложения.
Загрузка из .env (если есть), иначе — дефолты для Docker-окружения.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки MES-бота. Значения по умолчанию соответствуют Docker-compose."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL ───────────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5433
    DB_USER: str = "mes_user"
    DB_PASSWORD: str = "mes_password"
    DB_NAME: str = "mes_db"

    @property
    def DATABASE_URL(self) -> str:
        """Асинхронный DSN для asyncpg. Поддержка TCP и Unix-сокетов."""
        if self.DB_HOST.startswith("/"):
            # Cloud SQL Auth Proxy: подключение через Unix-сокет
            return (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@/{self.DB_NAME}?host={self.DB_HOST}"
            )
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # ── Telegram Bot ─────────────────────────────────────────────────────
    BOT_TOKEN: str = ""

    # Срок годности подписи initData Mini App (сек). 24 часа по умолчанию.
    WEBAPP_INIT_DATA_TTL: int = 86400

    # Telegram ID «корневых» админов через запятую — для первичной загрузки
    # (первый админ создаётся не из БД, а отсюда). Пример: "111,222".
    ADMIN_IDS: str = ""

    @property
    def admin_ids(self) -> set[int]:
        """Парсит ADMIN_IDS в множество int (пустые/мусорные значения пропускаются)."""
        ids: set[int] = set()
        for part in self.ADMIN_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
        return ids

    # ── FastAPI (Mini App) ───────────────────────────────────────────────
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000
    WEB_URL: str = "https://wvjxi-62-89-208-188.a.free.pinggy.link"

    # ── Webhook (Cloud Run) ──────────────────────────────────────────────
    WEBHOOK_SECRET: str = ""
    PORT: int = 8080




# Синглтон — импортируй из любого модуля
settings = Settings()
