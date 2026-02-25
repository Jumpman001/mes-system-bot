"""
Pydantic-схемы для Web API.
"""

from pydantic import BaseModel


class ReceiptCreate(BaseModel):
    """Схема создания записи прихода сырья."""
    material_name: str
    quantity: float
    unit: str
    batch_number: str | None = None
    telegram_id: int


class ChemistryLogCreate(BaseModel):
    """Схема ввода фактического расхода химии (Дозировщик)."""
    pipe_id: int
    stage: str  # liner, winder_fiberglass, winder_sand_1, winder_sand_2
    resin_kg: float
    cobalt_kg: float
    peroxide_kg: float
    telegram_id: int


class DryMaterialLogCreate(BaseModel):
    """Схема ввода фактического расхода сухих материалов (Технолог)."""
    pipe_id: int
    stage: str  # liner, winder

    # Материалы Лайнера
    polyester_gauze_m: float | None = None
    veil_m: float | None = None
    stitched_mat_kg: float | None = None
    ud300_m: float | None = None

    # Материалы Виндера
    fiberglass_2400tex_kg: float | None = None
    sand_kg: float | None = None
    ud250_m: float | None = None
    sand_gauze_m: float | None = None

    telegram_id: int


class LabTestCreate(BaseModel):
    """Схема ввода лабораторных тестов (Лаборант)."""
    pipe_id: int
    test_type: str  # gel_time_liner, gel_time_winder, sand_absorbency

    # Гелеобразование
    gel_time_minutes: float | None = None
    room_temperature_c: float | None = None
    exothermic_peak_c: float | None = None
    viscosity_mpa_s: float | None = None

    # Тест песка
    absorbency_result: str | None = None
    is_homogeneous: bool | None = None
    theoretical_resin_percent: float | None = None

    telegram_id: int


class QCPassportUpdate(BaseModel):
    """Схема обновления паспорта ОТК (Инженер ОТК)."""
    pipe_id: int

    # Шаг 3: Песок
    sand_layer_1_mm: float | None = None
    sand_layer_2_mm: float | None = None

    # Шаг 4: Разрешение на токарку
    turning_approved: bool | None = None

    # Шаг 5: Геометрия
    pipe_circumference_mm: float | None = None
    bell_circumference_mm: float | None = None
    outer_dn_mm: float | None = None
    wall_thickness_mm: float | None = None
    bell_wall_thickness_mm: float | None = None
    nipple_outer_diameter_mm: float | None = None
    channel_diameter_1_mm: float | None = None
    channel_diameter_2_mm: float | None = None
    channel_depth_mm: float | None = None
    channel_width_mm: float | None = None
    machined_length_mm: float | None = None

    # Шаг 6: Финал
    visual_inspection_notes: str | None = None
    final_verdict: str | None = None  # "passed" / "rejected"

    telegram_id: int


class PipeIdentificationCreate(BaseModel):
    """Схема присвоения серийного номера трубе (Инженер ОТК)."""
    pipe_id: int
    new_serial_number: str
    telegram_id: int
