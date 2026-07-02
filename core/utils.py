"""
Общие утилиты проекта.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import settings


def format_local_time(
    dt: datetime | None,
    tz_name: str | None = None,
) -> str:
    """
    Переводит timezone-aware datetime (UTC) в локальное время цеха
    (settings.TIMEZONE, если tz_name не передан) и возвращает строку
    вида DD.MM.YYYY HH:MM:SS.

    Если dt is None — возвращает прочерк.
    """
    if dt is None:
        return "—"
    local_dt = dt.astimezone(ZoneInfo(tz_name or settings.TIMEZONE))
    return local_dt.strftime("%d.%m.%Y %H:%M:%S")
