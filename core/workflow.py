"""
Производственный workflow трубы — ЕДИНЫЙ источник истины переходов статусов.

Раньше переходы были «зашиты» в двух местах: в STAGE_CONFIG бота
(bot/handlers/shift_leader.py) и в роуте ОТК (web/routes/qc.py). Теперь
вся доменная логика «какой статус идёт за каким» собрана здесь — чистые
данные и функции без БД и Telegram, поэтому их легко покрыть тестами.

Презентация (иконки, подписи кнопок) остаётся в боте — это слой UI.
"""

from db.models import FinalVerdict, PipeStatus, StageType

# ── Активная стадия для статуса ──────────────────────────────────────────────
# Если труба в этом статусе, начальник смены управляет указанной стадией.
STATUS_STAGE: dict[PipeStatus, StageType] = {
    PipeStatus.CREATED: StageType.LINER,
    PipeStatus.LINER: StageType.LINER,
    PipeStatus.LINER_DRYING: StageType.LINER_DRYING,
    PipeStatus.WINDER: StageType.WINDER,
    PipeStatus.WINDER_DRYING: StageType.WINDER_DRYING,
    PipeStatus.TURNING: StageType.TURNING,
    PipeStatus.EXTRACTION: StageType.EXTRACTION,
}

# ── Следующий статус после СТОП стадии ───────────────────────────────────────
NEXT_STATUS: dict[PipeStatus, PipeStatus] = {
    PipeStatus.CREATED: PipeStatus.LINER_DRYING,
    PipeStatus.LINER: PipeStatus.LINER_DRYING,
    PipeStatus.LINER_DRYING: PipeStatus.WINDER,
    PipeStatus.WINDER: PipeStatus.WINDER_DRYING,
    PipeStatus.WINDER_DRYING: PipeStatus.WAITING_QC_APPROVAL,
    PipeStatus.TURNING: PipeStatus.EXTRACTION,
    PipeStatus.EXTRACTION: PipeStatus.QC_FINAL,
}

# Статусы, которые начальник смены видит в очереди управления.
VISIBLE_STATUSES: list[PipeStatus] = [
    PipeStatus.CREATED,
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
    PipeStatus.TURNING,
    PipeStatus.EXTRACTION,
]


def stage_for(status: PipeStatus) -> StageType | None:
    """Стадия, которой управляет начальник смены в данном статусе (или None)."""
    return STATUS_STAGE.get(status)


def next_status_after_stop(status: PipeStatus) -> PipeStatus | None:
    """Статус трубы после остановки текущей стадии (или None, если перехода нет)."""
    return NEXT_STATUS.get(status)


def next_status_after_qc_approval(status: PipeStatus) -> PipeStatus | None:
    """
    После разрешения ОТК на токарку труба из ожидания переходит к токарке.
    Для прочих статусов разрешение статус не меняет (None).
    """
    if status == PipeStatus.WAITING_QC_APPROVAL:
        return PipeStatus.TURNING
    return None


def verdict_to_status(verdict: FinalVerdict) -> PipeStatus:
    """Финальный вердикт ОТК → итоговый статус трубы."""
    return (
        PipeStatus.ACCEPTED
        if verdict == FinalVerdict.PASSED
        else PipeStatus.REJECTED
    )
