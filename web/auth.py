"""
Аутентификация Telegram Mini App.

Проверяет подпись `initData` (HMAC-SHA256 по BOT_TOKEN), чтобы запросы
нельзя было подделать. Раньше клиент присылал `telegram_id` в теле запроса —
это недоверенные данные (initDataUnsafe). Теперь telegram_id берётся ТОЛЬКО
из подписанной строки initData и сверяется с пользователем в БД.

Алгоритм проверки — стандартный для Telegram Web Apps:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select

from core.config import settings
from db.database import async_session
from db.models import User, UserRole

logger = logging.getLogger(__name__)


def validate_init_data(init_data: str, bot_token: str, ttl_seconds: int) -> dict:
    """
    Проверяет подпись initData и его свежесть.
    Возвращает распарсенные данные (включая dict 'user').
    Бросает ValueError при любой проблеме (подделка, истёкший срок, мусор).
    """
    if not init_data:
        raise ValueError("Пустой initData")

    # parse_qsl сохраняет URL-декодирование значений
    parsed = dict(parse_qsl(init_data, strict_parsing=True))

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("В initData отсутствует hash")

    # data_check_string — все пары key=value (кроме hash), отсортированные по ключу
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    # secret_key = HMAC-SHA256(key="WebAppData", msg=bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # Сравнение, устойчивое к timing-атакам
    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Неверная подпись initData")

    # Проверка свежести (auth_date — unix-время выдачи)
    auth_date = parsed.get("auth_date")
    if auth_date is None:
        raise ValueError("В initData отсутствует auth_date")
    if time.time() - int(auth_date) > ttl_seconds:
        raise ValueError("initData устарел")

    # Распаковываем user (JSON-строка)
    user_raw = parsed.get("user")
    if not user_raw:
        raise ValueError("В initData отсутствует user")
    parsed["user"] = json.loads(user_raw)
    return parsed


async def get_current_user(authorization: str = Header(default="")) -> User:
    """
    FastAPI-зависимость: валидирует initData из заголовка
    `Authorization: tma <initData>`, находит пользователя в БД и проверяет,
    что он существует и активен. Возвращает модель User.
    """
    scheme, _, init_data = authorization.partition(" ")
    if scheme.lower() != "tma" or not init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация Telegram Mini App.",
        )

    if not settings.BOT_TOKEN:
        # Защита от мисконфигурации: без токена проверить подпись нельзя
        logger.error("BOT_TOKEN не задан — проверка initData невозможна.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Сервер не настроен для авторизации.",
        )

    try:
        data = validate_init_data(
            init_data, settings.BOT_TOKEN, settings.WEBAPP_INIT_DATA_TTL
        )
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Невалидный initData: %s", e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Невалидные данные авторизации.",
        )

    telegram_id = data["user"].get("id")
    if telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="В данных авторизации нет Telegram ID.",
        )

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не зарегистрирован или деактивирован.",
        )
    return user


def require_roles(*roles: UserRole):
    """
    Фабрика зависимостей: пускает только пользователей с одной из ролей
    (Администратор допускается всегда). Использование:

        user: User = Depends(require_roles(UserRole.QC_ENGINEER))
    """
    allowed = set(roles) | {UserRole.ADMIN}

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для этого действия.",
            )
        return user

    return _checker
