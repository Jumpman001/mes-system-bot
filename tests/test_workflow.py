"""
Тесты производственного workflow (core/workflow.py).
Чистая логика без БД и Telegram — быстрая и детерминированная.

Запуск: pytest tests/test_workflow.py
"""

from core.workflow import (
    NEXT_STATUS,
    STATUS_STAGE,
    VISIBLE_STATUSES,
    next_status_after_qc_approval,
    next_status_after_stop,
    stage_for,
    verdict_to_status,
)
from db.models import FinalVerdict, PipeStatus, StageType


def test_full_stop_chain():
    """Полная цепочка переходов по СТОП стадий до ожидания ОТК."""
    s = PipeStatus.CREATED
    chain = [s]
    # CREATED → LINER_DRYING → WINDER → WINDER_DRYING → WAITING_QC_APPROVAL
    while (nxt := next_status_after_stop(s)) is not None and nxt in NEXT_STATUS:
        s = nxt
        chain.append(s)
    assert chain == [
        PipeStatus.CREATED,
        PipeStatus.LINER_DRYING,
        PipeStatus.WINDER,
        PipeStatus.WINDER_DRYING,
    ]
    # следующий шаг — ожидание ОТК (это уже не «стадийный» статус)
    assert next_status_after_stop(PipeStatus.WINDER_DRYING) == PipeStatus.WAITING_QC_APPROVAL


def test_individual_stop_transitions():
    assert next_status_after_stop(PipeStatus.LINER) == PipeStatus.LINER_DRYING
    assert next_status_after_stop(PipeStatus.TURNING) == PipeStatus.EXTRACTION
    assert next_status_after_stop(PipeStatus.EXTRACTION) == PipeStatus.QC_FINAL


def test_stop_transition_absent_for_non_stage_statuses():
    """У статусов вне производственных стадий перехода по СТОП нет."""
    for status in (
        PipeStatus.PENDING_ID,
        PipeStatus.WAITING_QC_APPROVAL,
        PipeStatus.QC_FINAL,
        PipeStatus.ACCEPTED,
        PipeStatus.REJECTED,
    ):
        assert next_status_after_stop(status) is None


def test_stage_for():
    assert stage_for(PipeStatus.CREATED) == StageType.LINER
    assert stage_for(PipeStatus.WINDER_DRYING) == StageType.WINDER_DRYING
    assert stage_for(PipeStatus.ACCEPTED) is None


def test_qc_approval_transition():
    assert next_status_after_qc_approval(PipeStatus.WAITING_QC_APPROVAL) == PipeStatus.TURNING
    # разрешение в любом другом статусе статус не меняет
    assert next_status_after_qc_approval(PipeStatus.LINER) is None
    assert next_status_after_qc_approval(PipeStatus.TURNING) is None


def test_verdict_to_status():
    assert verdict_to_status(FinalVerdict.PASSED) == PipeStatus.ACCEPTED
    assert verdict_to_status(FinalVerdict.REJECTED) == PipeStatus.REJECTED


def test_tables_are_consistent():
    """Каждый «стадийный» статус имеет и стадию, и следующий статус."""
    assert set(STATUS_STAGE) == set(NEXT_STATUS)
    assert set(VISIBLE_STATUSES) == set(STATUS_STAGE)


def test_no_self_transition():
    """Стадия не переводит трубу саму в себя (нет залипания)."""
    for status, nxt in NEXT_STATUS.items():
        assert status != nxt
