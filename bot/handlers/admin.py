"""
Хэндлеры Администратора — Шаг 0: создание задачи и генерация труб.

FSM-состояния: DN → PN → SN → Length → WithSand → SandLayers → HasBell → Quantity → Photo → Confirm
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session
from db.models import Pipe, PipeStatus, Task

router = Router(name="admin")


# ── FSM-состояния ────────────────────────────────────────────────────────────

class NewTaskFSM(StatesGroup):
    """Машина состояний для создания новой задачи."""
    dn = State()             # Номинальный диаметр
    pn = State()             # Номинальное давление
    sn = State()             # Номинальная жёсткость
    length = State()         # Длина трубы (м)
    with_sand = State()      # С песком / без
    sand_layers = State()    # Кол-во слоёв песка (1 или 2)
    has_bell = State()       # Раструб/ниппель (да/нет)
    quantity = State()       # Кол-во труб
    photo = State()          # Фото-схема
    confirm = State()        # Подтверждение


# ── Хелперы ──────────────────────────────────────────────────────────────────

def _yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура Да / Нет."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"{prefix}:yes"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"{prefix}:no"),
        ]
    ])


def _sand_layers_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура 1 слой / 2 слоя."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 слой", callback_data="sand_layers:1"),
            InlineKeyboardButton(text="2 слоя", callback_data="sand_layers:2"),
        ]
    ])


def _confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура Подтвердить / Отмена."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="task_confirm:yes"),
            InlineKeyboardButton(text="🚫 Отмена", callback_data="task_confirm:no"),
        ]
    ])


def _generate_temp_serial(task_id: int, index: int) -> str:
    """Генерация временного серийного номера: TEMP-TASK{task_id}-{index}."""
    return f"TEMP-TASK{task_id}-{index}"


# ── Команда /new_task — старт FSM ───────────────────────────────────────────

@router.message(Command("new_task"))
async def cmd_new_task(message: Message, state: FSMContext) -> None:
    """Запуск создания новой задачи."""
    await state.clear()
    await state.set_state(NewTaskFSM.dn)
    await message.answer(
        "📋 <b>Создание новой задачи</b>\n\n"
        "Введите <b>DN</b> (номинальный диаметр, мм):",
        parse_mode="HTML",
    )


# ── Шаг 1: DN ───────────────────────────────────────────────────────────────

@router.message(NewTaskFSM.dn)
async def process_dn(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число для DN.")
        return
    await state.update_data(dn=int(message.text.strip()))
    await state.set_state(NewTaskFSM.pn)
    await message.answer("Введите <b>PN</b> (номинальное давление):", parse_mode="HTML")


# ── Шаг 2: PN ───────────────────────────────────────────────────────────────

@router.message(NewTaskFSM.pn)
async def process_pn(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число для PN.")
        return
    await state.update_data(pn=int(message.text.strip()))
    await state.set_state(NewTaskFSM.sn)
    await message.answer("Введите <b>SN</b> (номинальная жёсткость):", parse_mode="HTML")


# ── Шаг 3: SN ───────────────────────────────────────────────────────────────

@router.message(NewTaskFSM.sn)
async def process_sn(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число для SN.")
        return
    await state.update_data(sn=int(message.text.strip()))
    await state.set_state(NewTaskFSM.length)
    await message.answer("Введите <b>длину трубы</b> (м, можно дробное — например 6.0):", parse_mode="HTML")


# ── Шаг 4: Длина ────────────────────────────────────────────────────────────

@router.message(NewTaskFSM.length)
async def process_length(message: Message, state: FSMContext) -> None:
    try:
        length = float(message.text.strip().replace(",", "."))
        if length <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("⚠️ Введите положительное число для длины (например: 6.0).")
        return
    await state.update_data(length=length)
    await state.set_state(NewTaskFSM.with_sand)
    await message.answer(
        "Труба <b>с песком</b>?",
        parse_mode="HTML",
        reply_markup=_yes_no_keyboard("with_sand"),
    )


# ── Шаг 5: С песком / без ───────────────────────────────────────────────────

@router.callback_query(NewTaskFSM.with_sand, F.data.startswith("with_sand:"))
async def process_with_sand(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":")[1] == "yes"
    await state.update_data(with_sand=value)
    await callback.answer()

    if value:
        # С песком → спрашиваем количество слоёв
        await state.set_state(NewTaskFSM.sand_layers)
        await callback.message.edit_text(
            "Сколько <b>слоёв песка</b>?",
            parse_mode="HTML",
            reply_markup=_sand_layers_keyboard(),
        )
    else:
        # Без песка → пропускаем слои, идём к раструбу
        await state.update_data(sand_layers=0)
        await state.set_state(NewTaskFSM.has_bell)
        await callback.message.edit_text(
            "Труба с <b>раструбом / ниппелем</b>? (Или прямая?)",
            parse_mode="HTML",
            reply_markup=_yes_no_keyboard("has_bell"),
        )


# ── Шаг 6: Количество слоёв песка ───────────────────────────────────────────

@router.callback_query(NewTaskFSM.sand_layers, F.data.startswith("sand_layers:"))
async def process_sand_layers(callback: CallbackQuery, state: FSMContext) -> None:
    layers = int(callback.data.split(":")[1])
    await state.update_data(sand_layers=layers)
    await callback.answer()
    await state.set_state(NewTaskFSM.has_bell)
    await callback.message.edit_text(
        "Труба с <b>раструбом / ниппелем</b>? (Или прямая?)",
        parse_mode="HTML",
        reply_markup=_yes_no_keyboard("has_bell"),
    )


# ── Шаг 7: Раструб ─────────────────────────────────────────────────────────

@router.callback_query(NewTaskFSM.has_bell, F.data.startswith("has_bell:"))
async def process_has_bell(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":")[1] == "yes"
    await state.update_data(has_bell=value)
    await callback.answer()
    await state.set_state(NewTaskFSM.quantity)
    await callback.message.edit_text(
        "Введите <b>количество труб</b> в задаче:",
        parse_mode="HTML",
    )


# ── Шаг 8: Количество труб ──────────────────────────────────────────────────

@router.message(NewTaskFSM.quantity)
async def process_quantity(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip().isdigit() or int(message.text.strip()) < 1:
        await message.answer("⚠️ Введите целое положительное число.")
        return
    await state.update_data(quantity=int(message.text.strip()))
    await state.set_state(NewTaskFSM.photo)
    await message.answer(
        "📎 Отправьте <b>фото-схему</b> трубы (или напишите /skip, если нет):",
        parse_mode="HTML",
    )


# ── Шаг 9: Фото-схема ──────────────────────────────────────────────────────

@router.message(NewTaskFSM.photo, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    """Получаем фото-схему."""
    photo = message.photo[-1]  # наивысшее качество
    await state.update_data(photo_file_id=photo.file_id)
    await _show_summary(message, state)


@router.message(NewTaskFSM.photo, Command("skip"))
async def skip_photo(message: Message, state: FSMContext) -> None:
    """Пропуск фото-схемы."""
    await state.update_data(photo_file_id=None)
    await _show_summary(message, state)


@router.message(NewTaskFSM.photo)
async def photo_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("⚠️ Отправьте фото или напишите /skip.")


async def _show_summary(message: Message, state: FSMContext) -> None:
    """Показываем сводку перед подтверждением."""
    data = await state.get_data()
    await state.set_state(NewTaskFSM.confirm)

    sand_text = f"✅ Да ({data['sand_layers']} сл.)" if data["with_sand"] else "❌ Нет"
    bell_text = "✅ Да" if data["has_bell"] else "❌ Нет (прямая)"
    photo_text = "📷 Прикреплено" if data.get("photo_file_id") else "— нет"

    await message.answer(
        "📋 <b>Сводка задачи:</b>\n\n"
        f"• DN: <b>{data['dn']}</b>\n"
        f"• PN: <b>{data['pn']}</b>\n"
        f"• SN: <b>{data['sn']}</b>\n"
        f"• Длина: <b>{data['length']} м</b>\n"
        f"• Песок: {sand_text}\n"
        f"• Раструб: {bell_text}\n"
        f"• Количество труб: <b>{data['quantity']}</b>\n"
        f"• Фото-схема: {photo_text}\n\n"
        "Всё верно?",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard(),
    )


# ── Шаг 10: Подтверждение и сохранение ──────────────────────────────────────

@router.callback_query(NewTaskFSM.confirm, F.data == "task_confirm:yes")
async def confirm_task(callback: CallbackQuery, state: FSMContext) -> None:
    """Сохраняем задачу и генерируем трубы."""
    data = await state.get_data()
    await callback.answer("⏳ Сохраняю...")

    async with async_session() as session:
        # а) Создаём Task
        task = Task(
            dn=data["dn"],
            pn=data["pn"],
            sn=data["sn"],
            length=data["length"],
            with_sand=data["with_sand"],
            sand_layers=data["sand_layers"],
            has_bell=data["has_bell"],
            quantity=data["quantity"],
            created_by=callback.from_user.id,
        )
        session.add(task)
        await session.flush()  # получаем task.id

        # б) Генерируем N труб с временными serial_number (PENDING_ID)
        pipes = []
        for i in range(1, data["quantity"] + 1):
            serial = _generate_temp_serial(task.id, i)
            pipe = Pipe(
                task_id=task.id,
                serial_number=serial,
                status=PipeStatus.PENDING_ID,
            )
            pipes.append(pipe)

        session.add_all(pipes)
        await session.commit()

    # в) Ответ админу
    await callback.message.edit_text(
        f"✅ <b>Задача #{task.id} сохранена!</b>\n\n"
        f"Сгенерировано <b>{data['quantity']}</b> труб.\n"
        f"Они переданы в ОТК для присвоения серийных номеров.",
        parse_mode="HTML",
    )
    await state.clear()


@router.callback_query(NewTaskFSM.confirm, F.data == "task_confirm:no")
async def cancel_task(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена создания задачи."""
    await state.clear()
    await callback.answer("Отменено.")
    await callback.message.edit_text("🚫 Создание задачи отменено.")
