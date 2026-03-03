"""
Сервис работы со складом — автоматическое обновление остатков.

Используется из routes при приходе (receipt) и расходе (dosing, technologist).
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MaterialStock

logger = logging.getLogger(__name__)


async def update_stock(
    session: AsyncSession,
    material_name: str,
    quantity_delta: float,
    unit: str,
) -> None:
    """
    Обновляет остаток материала на складе.
    quantity_delta > 0 — приход, < 0 — расход.
    Создаёт запись MaterialStock, если её ещё нет.
    """
    result = await session.execute(
        select(MaterialStock).where(MaterialStock.material_name == material_name)
    )
    stock = result.scalar_one_or_none()

    if stock is None:
        stock = MaterialStock(
            material_name=material_name,
            unit=unit,
            current_quantity=max(quantity_delta, 0),
            min_quantity=0.0,
        )
        session.add(stock)
        logger.info("Склад: создан материал '%s', остаток: %.2f %s", material_name, quantity_delta, unit)
    else:
        stock.current_quantity += quantity_delta
        logger.info(
            "Склад: '%s' %+.2f %s → остаток: %.2f %s",
            material_name, quantity_delta, unit, stock.current_quantity, unit,
        )


# ── Маппинг: поле ChemistryLog → название материала на складе ────────────────

CHEMISTRY_STOCK_MAP = {
    "liner": {
        "resin_kg": ("Изофталевая смола (Лайнер)", "кг"),
        "cobalt_kg": ("Октоат кобальта 12%", "кг"),
        "peroxide_kg": ("Акперокс", "кг"),
    },
    "winder_fiberglass": {
        "resin_kg": ("Ортофталевая смола (Виндер и Песок)", "кг"),
        "cobalt_kg": ("Октоат кобальта 12%", "кг"),
        "peroxide_kg": ("Акперокс", "кг"),
    },
    "winder_sand_1": {
        "resin_kg": ("Ортофталевая смола (Виндер и Песок)", "кг"),
        "cobalt_kg": ("Октоат кобальта 12%", "кг"),
        "peroxide_kg": ("Акперокс", "кг"),
    },
    "winder_sand_2": {
        "resin_kg": ("Ортофталевая смола (Виндер и Песок)", "кг"),
        "cobalt_kg": ("Октоат кобальта 12%", "кг"),
        "peroxide_kg": ("Акперокс", "кг"),
    },
}


# ── Маппинг: поле DryMaterialLog → название материала на складе ──────────────

DRY_MATERIAL_STOCK_MAP = {
    "polyester_gauze_m": ("Марля полиэфирная (Лайнер)", "м"),
    "veil_m": ("PET50", "м"),
    "stitched_mat_kg": ("PET200", "кг"),
    "ud300_m": ("UD300", "м"),
    "fiberglass_2400tex_kg": ("Стекловолокно 2400tex", "кг"),
    "sand_kg": ("Песок", "кг"),
    "ud250_m": ("UD250", "м"),
    "sand_gauze_m": ("Марля полиэфирная (Песок)", "м"),
}


async def deduct_chemistry(session: AsyncSession, stage: str, data: dict) -> None:
    """Списать химию со склада при сохранении ChemistryLog."""
    mapping = CHEMISTRY_STOCK_MAP.get(stage, {})
    for field, (mat_name, unit) in mapping.items():
        value = data.get(field, 0) or 0
        if value > 0:
            await update_stock(session, mat_name, -value, unit)


async def deduct_dry_materials(session: AsyncSession, data: dict) -> None:
    """Списать сухие материалы со склада при сохранении DryMaterialLog."""
    for field, (mat_name, unit) in DRY_MATERIAL_STOCK_MAP.items():
        value = data.get(field, 0) or 0
        if value > 0:
            await update_stock(session, mat_name, -value, unit)
