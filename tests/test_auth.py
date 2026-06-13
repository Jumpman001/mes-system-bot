"""
Тесты валидации Telegram initData (web/auth.py).

Проверяем, что валидная подпись принимается, а подделка / подмена /
просроченные данные — отклоняются.

Запуск: pytest tests/test_auth.py
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from web.auth import validate_init_data

TOKEN = "123456:TEST_TOKEN_abcDEF"
TTL = 86400


def _make_init_data(token: str, user_id: int, auth_date: int) -> str:
    """Собирает корректно подписанный initData, как это делает клиент Telegram."""
    fields = {
        "user": json.dumps({"id": user_id, "first_name": "Test"}),
        "auth_date": str(auth_date),
        "query_id": "ABC123",
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(fields)


def test_valid_init_data_passes():
    data = validate_init_data(_make_init_data(TOKEN, 777, int(time.time())), TOKEN, TTL)
    assert data["user"]["id"] == 777


def test_forged_token_rejected():
    """Подпись чужим токеном не проходит проверку нашим токеном."""
    forged = _make_init_data("999:WRONG_TOKEN", 777, int(time.time()))
    with pytest.raises(ValueError):
        validate_init_data(forged, TOKEN, TTL)


def test_tampered_payload_rejected():
    """Подмена user_id после подписи ломает hash."""
    raw = _make_init_data(TOKEN, 777, int(time.time())).replace("777", "1")
    with pytest.raises(ValueError):
        validate_init_data(raw, TOKEN, TTL)


def test_expired_rejected():
    old = _make_init_data(TOKEN, 777, int(time.time()) - 100_000)
    with pytest.raises(ValueError):
        validate_init_data(old, TOKEN, TTL)


def test_missing_hash_rejected():
    with pytest.raises(ValueError):
        validate_init_data("user=%7B%7D&auth_date=123", TOKEN, TTL)


def test_empty_rejected():
    with pytest.raises(ValueError):
        validate_init_data("", TOKEN, TTL)
