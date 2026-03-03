"""
Хэндлер Досье на трубу — команда /pipe_report.
FSM: запрос серийного номера → поиск трубы → формирование детального HTML-отчёта.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from db.database import async_session
from db.models import Pipe


router = Router(name="report")


# ── FSM ──────────────────────────────────────────────────────────────────────

class PipeReportFSM(StatesGroup):
    """Машина состояний для получения досье на трубу."""
    serial_number = State()


# ── /pipe_report — старт FSM ────────────────────────────────────────────────

@router.message(Command("pipe_report"))
async def cmd_pipe_report(message: Message, state: FSMContext) -> None:
    """Запрос серийного номера для досье."""
    await state.clear()
    await state.set_state(PipeReportFSM.serial_number)
    await message.answer(
        "📑 <b>Досье на трубу</b>\n\n"
        "Введите <b>серийный номер</b> трубы:",
        parse_mode="HTML",
    )


# ── Ввод серийного номера → поиск и отчёт ───────────────────────────────────

@router.message(PipeReportFSM.serial_number)
async def process_serial_number(message: Message, state: FSMContext) -> None:
    """Ищем трубу и формируем досье."""
    user_input = (message.text or "").strip()

    # Если пользователь ввёл другую команду — отменяем FSM и не блокируем
    if user_input.startswith("/"):
        await state.clear()
        return

    if not user_input:
        await message.answer("⚠️ Введите серийный номер.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(Pipe)
            .options(
                joinedload(Pipe.task),
                joinedload(Pipe.stages),
                joinedload(Pipe.chemistry_logs),
                joinedload(Pipe.dry_material_logs),
                joinedload(Pipe.lab_tests),
                joinedload(Pipe.qc_passport),
            )
            .where(Pipe.serial_number == user_input)
        )
        pipe = result.unique().scalar_one_or_none()

    if not pipe:
        await message.answer(
            f"❌ Труба с номером <code>{user_input}</code> не найдена.\n"
            "Проверьте номер и попробуйте снова.",
            parse_mode="HTML",
        )
        return

    # ── Формируем досье ──────────────────────────────────────────────────
    lines = []

    # === Заголовок ===
    lines.append(f"📑 <b>ДОСЬЕ НА ТРУБУ</b>")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🔖 Серийный номер: <code>{pipe.serial_number}</code>")
    lines.append(f"📊 Статус: <b>{pipe.status.value}</b>")
    lines.append("")

    # === Данные задачи ===
    if pipe.task:
        t = pipe.task
        sand_text = f"✅ Да ({t.sand_layers} сл.)" if t.with_sand else "❌ Нет"
        bell_text = "✅ Да" if t.has_bell else "❌ Нет"
        lines.append("📋 <b>ЗАДАЧА</b>")
        lines.append(f"  • Задача: #{t.id}")
        lines.append(f"  • DN: <b>{t.dn}</b>")
        lines.append(f"  • PN: <b>{t.pn}</b>")
        lines.append(f"  • SN: <b>{t.sn}</b>")
        lines.append(f"  • Длина: {t.length} м")
        lines.append(f"  • Песок: {sand_text}")
        lines.append(f"  • Раструб: {bell_text}")
        lines.append("")

    # === Хронология стадий ===
    if pipe.stages:
        lines.append("🕐 <b>ХРОНОЛОГИЯ СТАДИЙ</b>")
        stage_names = {
            "liner": "Лайнер",
            "liner_drying": "Сушка лайнера",
            "winder": "Виндер",
            "winder_drying": "Сушка виндера",
            "turning": "Токарная",
            "extraction": "Трубосъем",
        }
        for s in pipe.stages:
            name = stage_names.get(s.stage.value, s.stage.value)
            start = s.start_time.strftime("%d.%m %H:%M") if s.start_time else "—"
            end = s.end_time.strftime("%d.%m %H:%M") if s.end_time else "—"
            lines.append(f"  • {name}: {start} → {end}")
        lines.append("")

    # === Итого химии ===
    if pipe.chemistry_logs:
        total_resin = sum(c.resin_kg or 0 for c in pipe.chemistry_logs)
        total_cobalt = sum(c.cobalt_kg or 0 for c in pipe.chemistry_logs)
        total_peroxide = sum(c.peroxide_kg or 0 for c in pipe.chemistry_logs)
        lines.append("🧪 <b>ИТОГО ХИМИИ</b>")
        lines.append(f"  • Смола: <b>{total_resin:.2f}</b> кг")
        lines.append(f"  • Кобальт: <b>{total_cobalt:.2f}</b> кг")
        lines.append(f"  • Пероксид: <b>{total_peroxide:.2f}</b> кг")
        lines.append("")

    # === Сухие материалы ===
    if pipe.dry_material_logs:
        lines.append("🧵 <b>СУХИЕ МАТЕРИАЛЫ</b>")
        for d in pipe.dry_material_logs:
            stage_name = "Лайнер" if d.stage.value == "liner" else "Виндер"
            lines.append(f"  <i>{stage_name}:</i>")
            if d.polyester_gauze_m:
                lines.append(f"    Полиэфирная марля: {d.polyester_gauze_m} м")
            if d.veil_m:
                lines.append(f"    Вуаль: {d.veil_m} м")
            if d.stitched_mat_kg:
                lines.append(f"    Сшитый материал: {d.stitched_mat_kg} кг")
            if d.ud300_m:
                lines.append(f"    UD300: {d.ud300_m} м")
            if d.fiberglass_2400tex_kg:
                lines.append(f"    Стекловолокно 2400tex: {d.fiberglass_2400tex_kg} кг")
            if d.sand_kg:
                lines.append(f"    Песок: {d.sand_kg} кг")
            if d.ud250_m:
                lines.append(f"    UD250: {d.ud250_m} м")
            if d.sand_gauze_m:
                lines.append(f"    Марля для песка: {d.sand_gauze_m} м")
        lines.append("")

    # === Результаты лаборатории ===
    if pipe.lab_tests:
        lines.append("🔬 <b>ЛАБОРАТОРНЫЕ ТЕСТЫ</b>")
        test_names = {
            "gel_time_liner": "Гелеобразование (Лайнер)",
            "gel_time_winder": "Гелеобразование (Виндер)",
            "sand_absorbency": "Впитываемость песка",
        }
        for lt in pipe.lab_tests:
            name = test_names.get(lt.test_type.value, lt.test_type.value)
            lines.append(f"  <i>{name}:</i>")
            if lt.gel_time_minutes is not None:
                lines.append(f"    Время гелеобр.: {lt.gel_time_minutes} мин")
            if lt.room_temperature_c is not None:
                lines.append(f"    Темп. в цеху: {lt.room_temperature_c} °C")
            if lt.exothermic_peak_c is not None:
                lines.append(f"    Экзотерм. пик: {lt.exothermic_peak_c} °C")
            if lt.viscosity_mpa_s is not None:
                lines.append(f"    Вязкость: {lt.viscosity_mpa_s} мПа·с")
            if lt.absorbency_result:
                lines.append(f"    Впитываемость: {lt.absorbency_result}")
            if lt.is_homogeneous is not None:
                homo = "✅ Да" if lt.is_homogeneous else "❌ Нет"
                lines.append(f"    Однородность: {homo}")
            if lt.theoretical_resin_percent is not None:
                lines.append(f"    Теор. % смолы: {lt.theoretical_resin_percent}%")
        lines.append("")

    # === Данные ОТК ===
    if pipe.qc_passport:
        p = pipe.qc_passport
        lines.append("📋 <b>ДАННЫЕ ОТК</b>")

        # Геометрия
        if p.pipe_circumference_mm is not None:
            lines.append(f"  • Окр. трубы: {p.pipe_circumference_mm} мм")
        if p.bell_circumference_mm is not None:
            lines.append(f"  • Окр. раструба: {p.bell_circumference_mm} мм")
        if p.wall_thickness_mm is not None:
            lines.append(f"  • Толщина стенки: {p.wall_thickness_mm} мм")
        if p.bell_wall_thickness_mm is not None:
            lines.append(f"  • Толщина стенки раструба: {p.bell_wall_thickness_mm} мм")
        if p.nipple_outer_diameter_mm is not None:
            lines.append(f"  • Наруж. ∅ ниппеля: {p.nipple_outer_diameter_mm} мм")
        if p.machined_length_mm is not None:
            lines.append(f"  • Длина обраб. части: {p.machined_length_mm} мм")

        # Песок
        if p.sand_layer_1_mm is not None:
            lines.append(f"  • Песок слой 1: {p.sand_layer_1_mm} мм")
        if p.sand_layer_2_mm is not None:
            lines.append(f"  • Песок слой 2: {p.sand_layer_2_mm} мм")

        # Токарка
        if p.turning_approved is not None:
            ta = "✅ Разрешена" if p.turning_approved else "❌ Не разрешена"
            lines.append(f"  • Токарка: {ta}")

        # Визуал
        if p.visual_inspection_notes:
            lines.append(f"  • Замечания: {p.visual_inspection_notes}")

        # Финальный вердикт
        if p.final_verdict:
            verdict_map = {"passed": "✅ ГОДЕН", "rejected": "❌ БРАК"}
            verdict_text = verdict_map.get(p.final_verdict.value, p.final_verdict.value)
            lines.append(f"\n🏆 <b>ФИНАЛЬНЫЙ ВЕРДИКТ: {verdict_text}</b>")
        lines.append("")

    # === Нет данных ===
    if not pipe.stages and not pipe.chemistry_logs and not pipe.lab_tests and not pipe.qc_passport:
        lines.append("ℹ️ <i>Данные производства ещё не внесены.</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    report = "\n".join(lines)
    await message.answer(report, parse_mode="HTML")
    await state.clear()
