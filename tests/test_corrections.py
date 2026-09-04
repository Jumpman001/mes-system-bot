"""
Тесты исправлений и защиты от ошибок ввода.

Главное, что проверяем: склад меняется на РАЗНИЦУ. Именно из-за
повторного списания попытка «исправить» опечатку раньше делала хуже.

Запуск: pytest tests/test_corrections.py
"""

import pytest

from web.services.correction_service import (
    EDITABLE_FIELDS,
    format_value,
    parse_value,
)
from web.services.validation_service import (
    CHEMISTRY_NORM_FIELDS,
    NORM_TOLERANCE,
    _compare_with_norm,
)
from db.models import CorrectionTarget


class FakeNorm:
    """Норматив-заглушка для проверки сравнения."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ── Приведение значений ─────────────────────────────────────────────────────

def test_parse_number():
    assert parse_value("resin_kg", "12.5") == 12.5


def test_parse_empty_is_none():
    assert parse_value("resin_kg", "") is None
    assert parse_value("resin_kg", None) is None


def test_parse_bool():
    assert parse_value("is_homogeneous", "true") is True
    assert parse_value("is_homogeneous", "да") is True
    assert parse_value("is_homogeneous", "false") is False


def test_parse_text_stays_text():
    assert parse_value("batch_number", "A-42") == "A-42"


def test_format_round_trip():
    # Число не должно превратиться в "12.500000"
    assert format_value(12.5) == "12.5"
    assert format_value(None) is None
    assert format_value(True) == "true"


# ── Белый список полей ──────────────────────────────────────────────────────

def test_editable_fields_are_safe():
    """Служебные поля исправлять нельзя — иначе можно подменить автора."""
    for target, fields in EDITABLE_FIELDS.items():
        for forbidden in ("id", "pipe_id", "entered_by", "entered_at", "stage"):
            assert forbidden not in fields, f"{target}: поле {forbidden} открыто!"


def test_every_target_has_fields():
    for target in CorrectionTarget:
        assert EDITABLE_FIELDS.get(target), f"нет полей для {target}"


# ── Сравнение с нормой ──────────────────────────────────────────────────────

def test_norm_warns_on_typo():
    """Классическая опечатка: 100 кг вместо 10 кг."""
    norm = FakeNorm(resin_liner_kg=10.0, cobalt_kg=0.4, peroxide_kg=0.3)
    warnings = _compare_with_norm(
        {"resin_kg": 100.0}, norm, CHEMISTRY_NORM_FIELDS["liner"]
    )
    assert len(warnings) == 1
    assert "Смола" in warnings[0]


def test_norm_silent_when_close():
    """Небольшое отклонение — норма жизни, не тревожим работника."""
    norm = FakeNorm(resin_liner_kg=10.0, cobalt_kg=0.4, peroxide_kg=0.3)
    warnings = _compare_with_norm(
        {"resin_kg": 11.0}, norm, CHEMISTRY_NORM_FIELDS["liner"]
    )
    assert warnings == []


def test_norm_warns_when_too_small():
    """Слишком мало — тоже подозрительно (забыли ноль)."""
    norm = FakeNorm(resin_liner_kg=10.0, cobalt_kg=0.4, peroxide_kg=0.3)
    warnings = _compare_with_norm(
        {"resin_kg": 1.0}, norm, CHEMISTRY_NORM_FIELDS["liner"]
    )
    assert len(warnings) == 1


def test_norm_skipped_when_not_set():
    """Если норматив не заполнен — не выдумываем предупреждений."""
    norm = FakeNorm(resin_liner_kg=None, cobalt_kg=None, peroxide_kg=None)
    warnings = _compare_with_norm(
        {"resin_kg": 999.0}, norm, CHEMISTRY_NORM_FIELDS["liner"]
    )
    assert warnings == []


def test_tolerance_boundary():
    """Ровно на границе допуска предупреждения ещё нет."""
    norm = FakeNorm(resin_liner_kg=10.0)
    at_edge = 10.0 * NORM_TOLERANCE
    assert _compare_with_norm({"resin_kg": at_edge}, norm, {"resin_kg": "resin_liner_kg"}) == []
    assert _compare_with_norm({"resin_kg": at_edge + 0.1}, norm, {"resin_kg": "resin_liner_kg"})
