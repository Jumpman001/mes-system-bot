"""
Хэндлеры Начальника смены — управление всеми производственными стадиями.

Стадии:
  1. Лайнер (Liner)           CREATED → LINER → LINER_DRYING
  2. Сушка Лайнера            LINER_DRYING → (start/stop drying) → WINDER
  3. Виндер (Winder)          WINDER → WINDER_DRYING
  4. Сушка Виндера             WINDER_DRYING → WAITING_QC_APPROVAL
  5. Токарка (Turning)        TURNING → EXTRACTION
  6. Трубосъем (Extraction)   EXTRACTION → QC_FINAL
"""

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.config import settings
from core.utils import format_local_time
from db.database import async_session
from db.models import Pipe, PipeStatus, ProductionStage, StageType

router = Router(name="shift_leader")


# ── Статусы, видимые начальнику смены ────────────────────────────────────────
VISIBLE_STATUSES = [
    PipeStatus.CREATED,
    PipeStatus.LINER,
    PipeStatus.LINER_DRYING,
    PipeStatus.WINDER,
    PipeStatus.WINDER_DRYING,
    PipeStatus.TURNING,
    PipeStatus.EXTRACTION,
]

# ── Маппинг стадий: статус → (StageType, следующий статус, название) ─────────
STAGE_CONFIG: dict[PipeStatus, dict] = {
    # Лайнер
    PipeStatus.CREATED: {
        "stage": StageType.LINER,
        "next": PipeStatus.LINER_DRYING,
        "label": "Лайнер",
        "icon": "⚪️",
    },
    PipeStatus.LINER: {
        "stage": StageType.LINER,
        "next": PipeStatus.LINER_DRYING,
        "label": "Лайнер",
        "icon": "🟢",
    },
    # Сушка Лайнера
    PipeStatus.LINER_DRYING: {
        "stage": StageType.LINER_DRYING,
        "next": PipeStatus.WINDER,
        "label": "Сушка Лайнера",
        "icon": "🟡",
    },
    # Виндер
    PipeStatus.WINDER: {
        "stage": StageType.WINDER,
        "next": PipeStatus.WINDER_DRYING,
        "label": "Виндер",
        "icon": "🔵",
    },
    # Сушка Виндера
    PipeStatus.WINDER_DRYING: {
        "stage": StageType.WINDER_DRYING,
        "next": PipeStatus.WAITING_QC_APPROVAL,
        "label": "Сушка Виндера",
        "icon": "🟠",
    },
    # Токарка
    PipeStatus.TURNING: {
        "stage": StageType.TURNING,
        "next": PipeStatus.EXTRACTION,
        "label": "Токарка",
        "icon": "🟣",
    },
    # Трубосъем
    PipeStatus.EXTRACTION: {
        "stage": StageType.EXTRACTION,
        "next": PipeStatus.QC_FINAL,
        "label": "Трубосъем",
        "icon": "🔴",
    },
}

# Статусы, при которых начальник смены нажимает СТАРТ (нет активной стадии)
START_STATUSES = {
    PipeStatus.CREATED,      # → Старт Лайнера
    PipeStatus.LINER_DRYING,  # → Старт Сушки Лайнера (если нет активной)
    PipeStatus.WINDER,        # → Старт Виндера
    PipeStatus.WINDER_DRYING, # → Старт Сушки Виндера
    PipeStatus.TURNING,       # → Старт Токарки
    PipeStatus.EXTRACTION,    # → Старт Трубосъема
}

# Статусы, при которых идёт процесс и доступен СТОП
RUNNING_STATUSES = {
    PipeStatus.LINER,  # → Стоп Лайнера
}


# ── /work — список труб ─────────────────────────────────────────────────────

@router.message(Command("work"))
async def cmd_work(message: Message) -> None:
    """Показать трубы, доступные для управления."""
    async with async_session() as session:
        result = await session.execute(
            select(Pipe)
            .options(selectinload(Pipe.task), selectinload(Pipe.stages))
            .where(Pipe.status.in_(VISIBLE_STATUSES))
            .order_by(Pipe.id)
        )
        pipes = result.scalars().all()

    if not pipes:
        await message.answer("📭 Нет труб для управления.")
        return

    await message.answer(
        "🏭 <b>Трубы для управления:</b>\n"
        "Нажмите на трубу для управления.",
        parse_mode="HTML",
        reply_markup=_build_pipe_list_keyboard(pipes),
    )


def _build_pipe_list_keyboard(pipes: list[Pipe]) -> InlineKeyboardMarkup:
    """Список кнопок с серийниками и иконками статуса."""
    buttons = []
    for pipe in pipes:
        cfg = STAGE_CONFIG.get(pipe.status)
        icon = cfg["icon"] if cfg else "⚪️"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {pipe.serial_number}",
                callback_data=f"pipe_select:{pipe.id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Выбор трубы → меню управления ────────────────────────────────────────────

@router.callback_query(F.data.startswith("pipe_select:"))
async def select_pipe(callback: CallbackQuery) -> None:
    """Показать меню управления конкретной трубой."""
    pipe_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        pipe = await session.get(Pipe, pipe_id)
        if not pipe:
            await callback.answer("❌ Труба не найдена.", show_alert=True)
            return

        has_active_stage = await _has_active_stage(session, pipe)

    await callback.answer()

    cfg = STAGE_CONFIG.get(pipe.status)
    if cfg:
        if pipe.status in RUNNING_STATUSES or has_active_stage:
            label = f"{cfg['icon']} {cfg['label']} (в процессе)"
        else:
            label = f"{cfg['icon']} Ожидает: {cfg['label']}"
    else:
        label = pipe.status.value

    keyboard = _build_pipe_control_keyboard(pipe, has_active_stage)
    await callback.message.edit_text(
        f"🔧 <b>Труба: {pipe.serial_number}</b>\n"
        f"Статус: {label}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def _has_active_stage(session, pipe: Pipe) -> bool:
    """Проверяет, есть ли активная (незакрытая) стадия для текущего статуса."""
    cfg = STAGE_CONFIG.get(pipe.status)
    if not cfg:
        return False
    result = await session.execute(
        select(ProductionStage).where(
            ProductionStage.pipe_id == pipe.id,
            ProductionStage.stage == cfg["stage"],
            ProductionStage.end_time.is_(None),
        )
    )
    return result.scalar_one_or_none() is not None


def _build_pipe_control_keyboard(pipe: Pipe, has_active_stage: bool) -> InlineKeyboardMarkup:
    """Формирует кнопки Start/Stop в зависимости от статуса."""
    buttons = []
    cfg = STAGE_CONFIG.get(pipe.status)

    if cfg:
        if pipe.status in RUNNING_STATUSES or has_active_stage:
            # Стадия запущена → кнопка СТОП
            buttons.append([InlineKeyboardButton(
                text=f"⏹ Стоп: {cfg['label']}",
                callback_data=f"stage_stop:{pipe.id}",
            )])
        else:
            # Стадия НЕ запущена → кнопка СТАРТ
            buttons.append([InlineKeyboardButton(
                text=f"▶️ Старт: {cfg['label']}",
                callback_data=f"stage_start:{pipe.id}",
            )])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Универсальный СТАРТ стадии ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("stage_start:"))
async def start_stage(callback: CallbackQuery) -> None:
    """Универсальный обработчик запуска любой стадии."""
    pipe_id = int(callback.data.split(":")[1])
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        pipe = await session.get(Pipe, pipe_id)
        cfg = STAGE_CONFIG.get(pipe.status) if pipe else None

        if not pipe or not cfg:
            await callback.answer("⚠️ Невозможно запустить стадию.", show_alert=True)
            return

        # Проверяем, нет ли уже активной стадии
        if await _has_active_stage(session, pipe):
            await callback.answer("⚠️ Стадия уже запущена.", show_alert=True)
            return

        stage = ProductionStage(
            pipe_id=pipe.id,
            stage=cfg["stage"],
            start_time=now,
            started_by=callback.from_user.id,
        )
        session.add(stage)

        # Для CREATED → переводим в LINER (стадия активна)
        if pipe.status == PipeStatus.CREATED:
            pipe.status = PipeStatus.LINER

        await session.commit()
        # Обновляем cfg для нового статуса после commit
        new_cfg = STAGE_CONFIG.get(pipe.status, cfg)

    await callback.answer(f"✅ {cfg['label']} запущен!")
    await callback.message.edit_text(
        f"🔧 <b>Труба: {pipe.serial_number}</b>\n"
        f"Статус: {new_cfg['icon']} {cfg['label']} (в процессе)\n\n"
        f"▶️ Запущен: {format_local_time(now)}",
        parse_mode="HTML",
        reply_markup=_build_pipe_control_keyboard(pipe, has_active_stage=True),
    )


# ── Универсальный СТОП стадии ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("stage_stop:"))
async def stop_stage(callback: CallbackQuery) -> None:
    """Универсальный обработчик остановки любой стадии."""
    pipe_id = int(callback.data.split(":")[1])
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        pipe = await session.get(Pipe, pipe_id)
        cfg = STAGE_CONFIG.get(pipe.status) if pipe else None

        if not pipe or not cfg:
            await callback.answer("⚠️ Невозможно остановить стадию.", show_alert=True)
            return

        # Находим активную запись стадии
        result = await session.execute(
            select(ProductionStage).where(
                ProductionStage.pipe_id == pipe.id,
                ProductionStage.stage == cfg["stage"],
                ProductionStage.end_time.is_(None),
            )
        )
        stage = result.scalar_one_or_none()
        if not stage:
            await callback.answer("⚠️ Нет активной стадии.", show_alert=True)
            return

        stage.end_time = now
        stage.stopped_by = callback.from_user.id

        # Вычисляем длительность
        duration = ""
        if stage.start_time:
            delta = now - stage.start_time
            minutes = int(delta.total_seconds() // 60)
            seconds = int(delta.total_seconds() % 60)
            duration = f"\n⏱ Длительность: {minutes} мин {seconds} сек"

        # Переводим трубу в следующий статус
        next_status = cfg["next"]
        pipe.status = next_status
        await session.commit()

    # Определяем, что показывать дальше
    next_cfg = STAGE_CONFIG.get(next_status)
    if next_status == PipeStatus.WAITING_QC_APPROVAL:
        next_hint = "⏳ Ожидает разрешения ОТК."
    elif next_status == PipeStatus.QC_FINAL:
        next_hint = "🔍 Передана на финальный контроль ОТК."
    elif next_cfg:
        next_hint = f"➡️ Готова к стадии: {next_cfg['label']}."
    else:
        next_hint = ""

    await callback.answer(f"✅ {cfg['label']} завершён!")
    await callback.message.edit_text(
        f"🔧 <b>Труба: {pipe.serial_number}</b>\n\n"
        f"⏹ {cfg['label']} завершён: {format_local_time(now)}{duration}\n"
        f"{next_hint}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
        ]),
    )


# ── Назад к списку труб ─────────────────────────────────────────────────────

@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(Pipe)
            .options(selectinload(Pipe.task), selectinload(Pipe.stages))
            .where(Pipe.status.in_(VISIBLE_STATUSES))
            .order_by(Pipe.id)
        )
        pipes = result.scalars().all()

    if not pipes:
        await callback.message.edit_text("📭 Нет труб для управления.")
        await callback.answer()
        return

    await callback.message.edit_text(
        "🏭 <b>Трубы для управления:</b>\n"
        "Нажмите на трубу для управления.",
        parse_mode="HTML",
        reply_markup=_build_pipe_list_keyboard(pipes),
    )
    await callback.answer()


# ── /receipt — вход в Mini App для прихода сырья ─────────────────────────────

@router.message(Command("receipt"))
async def cmd_receipt(message: Message) -> None:
    """Открывает Mini App для ввода прихода сырья на склад."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📦 Открыть форму прихода",
            web_app=WebAppInfo(url=f"{settings.WEB_URL}/receipt"),
        )]
    ])
    await message.answer(
        "📦 <b>Ввод ежедневного прихода сырья на склад</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть форму ввода.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
