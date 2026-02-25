"""
Общие утилиты проекта.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def format_local_time(
    dt: datetime | None,
    tz_name: str = "Asia/Dushanbe",
) -> str:
    """
    Переводит timezone-aware datetime (UTC) в локальное время
    и возвращает строку вида DD.MM.YYYY HH:MM:SS.

    Если dt is None — возвращает прочерк.
    """
    if dt is None:
        return "—"
    local_dt = dt.astimezone(ZoneInfo(tz_name))
    return local_dt.strftime("%d.%m.%Y %H:%M:%S")
