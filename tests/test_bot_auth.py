"""
Тесты авторизации бота (bot/auth.py, core/config.py).
Проверяют чистую логику: разбор ADMIN_IDS и правило допуска по ролям.

Запуск: pytest tests/test_bot_auth.py
"""

from bot.auth import is_role_allowed
from core.config import Settings
from db.models import UserRole


def test_admin_ids_parsing():
    s = Settings(ADMIN_IDS="111, 222 ,333")
    assert s.admin_ids == {111, 222, 333}


def test_admin_ids_ignores_junk_and_empty():
    assert Settings(ADMIN_IDS="").admin_ids == set()
    assert Settings(ADMIN_IDS="abc, 10, , -5").admin_ids == {10}


def test_admin_always_allowed():
    # Админ проходит любую проверку роли
    assert is_role_allowed(UserRole.ADMIN, (UserRole.SHIFT_LEADER,))
    assert is_role_allowed(UserRole.ADMIN, (UserRole.QC_ENGINEER,))


def test_matching_role_allowed():
    assert is_role_allowed(UserRole.SHIFT_LEADER, (UserRole.SHIFT_LEADER,))


def test_wrong_role_rejected():
    assert not is_role_allowed(UserRole.LAB_TECHNICIAN, (UserRole.SHIFT_LEADER,))
    assert not is_role_allowed(UserRole.OPERATOR, (UserRole.ADMIN,))


def test_none_role_rejected():
    assert not is_role_allowed(None, (UserRole.ADMIN,))
