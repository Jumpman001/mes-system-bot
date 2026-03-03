"""
MES-система для производства стеклопластиковых труб.
SQLAlchemy 2.0 (asyncio) модели — полностью отражают Workflow из claude.md.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# ── Базовый класс ──────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


# ── Enums ───────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    """Роли пользователей (7 ролей)."""
    ADMIN = "admin"                    # Администратор
    QC_ENGINEER = "qc_engineer"        # Инженер ОТК
    SHIFT_LEADER = "shift_leader"      # Начальник смены
    DOSING_OPERATOR = "dosing_operator" # Дозировщик
    LAB_TECHNICIAN = "lab_technician"  # Лаборант
    TECHNOLOGIST = "technologist"      # Технолог
    OPERATOR = "operator"              # Оператор


class PipeStatus(str, enum.Enum):
    """Статус трубы в производственном цикле."""
    PENDING_ID = "pending_id"                    # Ожидает присвоения серийного номера от ОТК
    CREATED = "created"                          # Создана (Шаг 0)
    LINER = "liner"                              # Лайнер (Шаг 1)
    LINER_DRYING = "liner_drying"                # Сушка после лайнера (Шаг 2)
    WINDER = "winder"                            # Виндер (Шаг 3)
    WINDER_DRYING = "winder_drying"              # Сушка после виндера (Шаг 4)
    WAITING_QC_APPROVAL = "waiting_qc_approval"  # Ожидание разрешения ОТК (Шаг 4)
    TURNING = "turning"                          # Токарная обработка (Шаг 5)
    EXTRACTION = "extraction"                    # Трубосъем (Шаг 6)
    QC_FINAL = "qc_final"                        # Финальный ОТК (Шаг 6)
    ACCEPTED = "accepted"                        # Годен к выпуску
    REJECTED = "rejected"                        # Брак


class StageType(str, enum.Enum):
    """Тип производственной стадии (6 стадий)."""
    LINER = "liner"
    LINER_DRYING = "liner_drying"
    WINDER = "winder"
    WINDER_DRYING = "winder_drying"
    TURNING = "turning"
    EXTRACTION = "extraction"


class ChemistryStage(str, enum.Enum):
    """К какой стадии/подстадии относится запись химии (Дозировщик)."""
    LINER = "liner"                     # Химия на Лайнер
    WINDER_FIBERGLASS = "winder_fiberglass"  # Виндер — стекловолокно
    WINDER_SAND_1 = "winder_sand_1"     # Виндер — Песок 1
    WINDER_SAND_2 = "winder_sand_2"     # Виндер — Песок 2


class DryMaterialStage(str, enum.Enum):
    """К какой стадии относится запись сухих материалов (Технолог)."""
    LINER = "liner"
    WINDER = "winder"


class LabTestType(str, enum.Enum):
    """Тип лабораторного теста (Лаборант)."""
    GEL_TIME_LINER = "gel_time_liner"             # Время гелеобразования — Лайнер
    GEL_TIME_WINDER = "gel_time_winder"           # Время гелеобразования — Виндер
    SAND_ABSORBENCY = "sand_absorbency"           # Тест впитываемости и однородности песка


class FinalVerdict(str, enum.Enum):
    """Финальный статус ОТК."""
    PASSED = "passed"       # Годен к выпуску
    REJECTED = "rejected"   # Брак


# ── Пользователи ────────────────────────────────────────────────────────────

class User(Base):
    """Пользователь системы, авторизация по Telegram ID."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Задачи (Заказы) ─────────────────────────────────────────────────────────

class Task(Base):
    """
    Общий заказ от Администратора (Шаг 0).
    Содержит параметры партии: DN, PN, SN, длина, тип трубы, количество.
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Параметры заказа
    dn: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номинальный диаметр (DN)")
    pn: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номинальное давление (PN)")
    sn: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номинальная жесткость (SN)")
    length: Mapped[float] = mapped_column(Float, nullable=False, comment="Длина трубы, м")
    with_sand: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="Тип: с песком / без")
    sand_layers: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Количество слоев песка (0, 1 или 2)"
    )
    has_bell: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="Наличие раструба/ниппеля (True) или прямая труба (False)"
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="Количество труб")

    created_by: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Telegram ID администратора"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Связь One-to-Many → Pipes
    pipes: Mapped[List["Pipe"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="selectin"
    )


# ── Трубы ────────────────────────────────────────────────────────────────────

class Pipe(Base):
    """
    Конкретная труба с уникальным серийным номером (Шаг 0).
    Генерирует ОТК после создания задачи.
    """
    __tablename__ = "pipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    serial_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="Уникальный серийный номер, генерируется ОТК"
    )
    status: Mapped[PipeStatus] = mapped_column(
        Enum(PipeStatus, native_enum=False), nullable=False, default=PipeStatus.CREATED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Обратные связи
    task: Mapped["Task"] = relationship(back_populates="pipes")
    stages: Mapped[List["ProductionStage"]] = relationship(
        back_populates="pipe", cascade="all, delete-orphan", lazy="selectin"
    )
    chemistry_logs: Mapped[List["ChemistryLog"]] = relationship(
        back_populates="pipe", cascade="all, delete-orphan", lazy="selectin"
    )
    dry_material_logs: Mapped[List["DryMaterialLog"]] = relationship(
        back_populates="pipe", cascade="all, delete-orphan", lazy="selectin"
    )
    lab_tests: Mapped[List["LabTest"]] = relationship(
        back_populates="pipe", cascade="all, delete-orphan", lazy="selectin"
    )
    qc_passport: Mapped[Optional["QCPassport"]] = relationship(
        back_populates="pipe", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


# ── Производственные стадии ──────────────────────────────────────────────────

class ProductionStage(Base):
    """
    Таймстемпы СТАРТ/СТОП для каждой из 6 стадий (Шаги 1-6).
    Начальник смены управляет запуском и остановкой.
    """
    __tablename__ = "production_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipe_id: Mapped[int] = mapped_column(
        ForeignKey("pipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[StageType] = mapped_column(
        Enum(StageType, native_enum=False), nullable=False
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Время старта стадии"
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Время остановки стадии"
    )
    started_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Telegram ID нач. смены (СТАРТ)"
    )
    stopped_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Telegram ID нач. смены (СТОП)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pipe: Mapped["Pipe"] = relationship(back_populates="stages")


# ── Учёт «мокрой» химии (Дозировщик) ────────────────────────────────────────

class ChemistryLog(Base):
    """
    Фактический расход химических материалов (Дозировщик, Шаги 2-3).
    Разделение по стадиям: Лайнер, Виндер-Стекловолокно, Виндер-Песок1, Виндер-Песок2.
    """
    __tablename__ = "chemistry_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipe_id: Mapped[int] = mapped_column(
        ForeignKey("pipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[ChemistryStage] = mapped_column(
        Enum(ChemistryStage, native_enum=False), nullable=False,
        comment="Стадия/подстадия: liner, winder_fiberglass, winder_sand_1, winder_sand_2"
    )

    # Изофталевая (или орто-/другие) смола, кг
    resin_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Фактический расход смолы, кг"
    )
    # Октоат кобальта 12 %, кг
    cobalt_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Октоат кобальта 12 %, кг"
    )
    # Акперокс (пероксид), кг
    peroxide_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Акперокс (пероксид), кг"
    )

    entered_by: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Telegram ID дозировщика"
    )
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pipe: Mapped["Pipe"] = relationship(back_populates="chemistry_logs")


# ── Учёт «сухих» материалов (Технолог) ──────────────────────────────────────

class DryMaterialLog(Base):
    """
    Фактический расход сухих материалов (Технолог, Шаги 2-3).
    Разделение по стадиям: Лайнер, Виндер.
    """
    __tablename__ = "dry_material_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipe_id: Mapped[int] = mapped_column(
        ForeignKey("pipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[DryMaterialStage] = mapped_column(
        Enum(DryMaterialStage, native_enum=False), nullable=False,
        comment="Стадия: liner или winder"
    )

    # ── Материалы стадии Лайнер ──
    polyester_gauze_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Полиэфирная марля, м (Лайнер)"
    )
    veil_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Вуаль, м (Лайнер)"
    )
    stitched_mat_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Сшитый материал, кг (Лайнер)"
    )
    ud300_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="UD300, м (Лайнер)"
    )

    # ── Материалы стадии Виндер ──
    fiberglass_2400tex_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Стекловолокно 2400tex, кг (Виндер)"
    )
    sand_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Песок, кг (Виндер)"
    )
    ud250_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="UD250, м (Виндер)"
    )
    sand_gauze_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Марля для песка, м (Виндер)"
    )

    entered_by: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Telegram ID технолога"
    )
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pipe: Mapped["Pipe"] = relationship(back_populates="dry_material_logs")


# ── Лабораторные тесты (Лаборант) ───────────────────────────────────────────

class LabTest(Base):
    """
    Лабораторные тесты (Лаборант, Шаги 1, 3).
    - Гелеобразование лайнера (Шаг 1)
    - Гелеобразование виндера (Шаг 3)
    - Впитываемость и однородность песка (Шаг 3)
    """
    __tablename__ = "lab_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipe_id: Mapped[int] = mapped_column(
        ForeignKey("pipes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_type: Mapped[LabTestType] = mapped_column(
        Enum(LabTestType, native_enum=False), nullable=False,
        comment="Тип теста: gel_time_liner, gel_time_winder, sand_absorbency"
    )

    # Время гелеобразования (для gel_time_liner, gel_time_winder)
    gel_time_minutes: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Время гелеобразования, мин"
    )
    room_temperature_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Температура в цеху, °C"
    )
    exothermic_peak_c: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Температура экзотермического пика, °C"
    )
    viscosity_mpa_s: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Вязкость, мПа·с"
    )

    # Тест впитываемости / однородности песка
    absorbency_result: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Результат теста впитываемости (текстовое описание)"
    )
    is_homogeneous: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="Однородность смеси: True/False"
    )
    theoretical_resin_percent: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Теор. % смолы в песке"
    )

    entered_by: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="Telegram ID лаборанта"
    )
    entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    pipe: Mapped["Pipe"] = relationship(back_populates="lab_tests")


# ── Паспорт ОТК ─────────────────────────────────────────────────────────────

class QCPassport(Base):
    """
    Данные инженера ОТК: толщины песчаных слоёв (Шаг 3), разрешение на токарку (Шаг 4),
    геометрия токарки (Шаг 5), визуальный контроль и финальный статус (Шаг 6).
    Связь One-to-One с Pipe.
    """
    __tablename__ = "qc_passports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipe_id: Mapped[int] = mapped_column(
        ForeignKey("pipes.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    # ── Шаг 3. Толщина песчаных слоёв (замеряет ОТК во время Виндера) ──
    sand_layer_1_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Толщина 1-го слоя песка, мм"
    )
    sand_layer_2_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Толщина 2-го слоя песка, мм"
    )

    # ── Шаг 4. Разрешение ОТК на токарную обработку ──
    turning_approved: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="Разрешение на токарку (True/False)"
    )
    turning_approved_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Telegram ID инженера ОТК, давшего разрешение"
    )
    turning_approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Дата/время разрешения"
    )

    # ── Шаг 5. Геометрия токарной обработки (вводит ОТК) ──
    pipe_circumference_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Длина окружности трубы, мм"
    )
    bell_circumference_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Длина окружности раструба, мм"
    )
    wall_thickness_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Толщина стенки, мм"
    )
    bell_wall_thickness_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Толщина стенки раструба, мм"
    )
    nipple_outer_diameter_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Наружный диаметр ниппеля, мм"
    )
    channel_diameter_1_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Диаметр канала 1, мм"
    )
    channel_diameter_2_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Диаметр канала 2, мм (если есть)"
    )
    channel_depth_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Глубина каналов, мм"
    )
    channel_width_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Ширина каналов, мм"
    )
    machined_length_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Длина обработанной части, мм"
    )
    geometry_entered_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Telegram ID инженера ОТК (геометрия)"
    )
    geometry_entered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Дата/время ввода геометрии"
    )

    # ── Шаг 6. Визуальный контроль и финальный вердикт ──
    visual_inspection_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Замечания визуального контроля (дефекты)"
    )
    final_verdict: Mapped[Optional[FinalVerdict]] = mapped_column(
        Enum(FinalVerdict, native_enum=False), nullable=True,
        comment="Финальный статус: passed / rejected"
    )
    verdict_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="Telegram ID инженера ОТК (финал)"
    )
    verdict_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Дата/время финального решения"
    )

    pipe: Mapped["Pipe"] = relationship(back_populates="qc_passport")

# ── Приход сырья на склад (Начальник смены) ────────────────────────────────

class MaterialReceipt(Base):
    """
    Ежедневный приход сырья на склад цеха (Шаг 1).
    Заполняет Начальник смены через Mini App.
    """
    __tablename__ = "material_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Названия материалов (можно сделать Enum, но пока оставим String для гибкости)
    material_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Название сырья (Смола, Песок и т.д.)")
    quantity: Mapped[float] = mapped_column(Float, nullable=False, comment="Количество прихода")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, comment="Единица измерения (кг, м, шт)")
    
    batch_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Номер партии поставщика")
    
    entered_by: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Telegram ID начальника смены")
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Склад — текущие остатки материалов ──────────────────────────────────────

class MaterialStock(Base):
    """
    Текущий остаток каждого материала на складе.
    Обновляется автоматически:
      + при приходе (MaterialReceipt)
      − при расходе (ChemistryLog, DryMaterialLog)
    """
    __tablename__ = "material_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="Название материала (совпадает с MaterialReceipt)"
    )
    unit: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Единица измерения (кг, м, шт)"
    )
    current_quantity: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="Текущий остаток"
    )
    min_quantity: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Минимальный порог (для алерта «заканчивается»)"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Нормативы расхода на тип трубы ─────────────────────────────────────────

class PipeNorm(Base):
    """
    Норматив расхода материалов на 1 трубу заданного типа (DN/PN/SN).
    Используется для сравнения факта с нормой и расчёта
    ожидаемого расхода склада при создании задачи.
    """
    __tablename__ = "pipe_norms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Тип трубы
    dn: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номинальный диаметр")
    pn: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номинальное давление")
    sn: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номинальная жёсткость")
    with_sand: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="С песком / без песка"
    )

    # ── Нормы расхода химии (кг на 1 трубу) ──
    resin_liner_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Смола на Лайнер, кг"
    )
    resin_winder_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Смола на Виндер (стекло), кг"
    )
    resin_sand_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Смола на Песок, кг"
    )
    cobalt_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Октоат кобальта, кг"
    )
    peroxide_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Акперокс, кг"
    )

    # ── Нормы расхода сухих материалов ──
    polyester_gauze_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Полиэфирная марля, м"
    )
    veil_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Вуаль, м"
    )
    stitched_mat_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Сшитый материал, кг"
    )
    ud300_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="UD300, м"
    )
    fiberglass_2400tex_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Стекловолокно 2400tex, кг"
    )
    sand_kg: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Песок, кг"
    )
    ud250_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="UD250, м"
    )
    sand_gauze_m: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Марля для песка, м"
    )

    # ── Допуски геометрии (мин / макс) ──
    wall_thickness_min_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Толщина стенки мин, мм"
    )
    wall_thickness_max_mm: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Толщина стенки макс, мм"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )