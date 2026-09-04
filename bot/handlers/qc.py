"""
Хэндлеры Инженера ОТК — паспорт качества и присвоение серийных номеров.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import open_webapp
from db.models import UserRole

router = Router(name="qc")

QC_ROLES = (UserRole.QC_ENGINEER,)


@router.message(Command("qc_passport"))
async def cmd_qc_passport(message: Message) -> None:
    """Кнопка Mini App для заполнения паспорта ОТК."""
    await open_webapp(
        message,
        path="/qc",
        title="🛂 Паспорт ОТК",
        description="Замеры песка, разрешение на токарку, геометрия и финальный вердикт.",
        button="Открыть паспорт",
        roles=QC_ROLES,
    )


@router.message(Command("naming"))
async def cmd_naming(message: Message) -> None:
    """Кнопка Mini App для присвоения серийных номеров."""
    await open_webapp(
        message,
        path="/qc_naming",
        title="🏷 Серийные номера",
        description="Присвойте постоянные номера трубам из новой задачи.",
        button="Открыть форму",
        roles=QC_ROLES,
    )
