"""
Хэндлер Дозировщика — команда /chemistry открывает форму расхода химии.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import open_webapp
from db.models import UserRole

router = Router(name="dosing")


@router.message(Command("chemistry"))
async def cmd_chemistry(message: Message) -> None:
    """Кнопка Mini App для ввода фактического расхода химии."""
    await open_webapp(
        message,
        path="/dosing",
        title="🧪 Расход химии",
        description="Внесите фактический расход смолы, кобальта и акперокса.",
        button="Открыть форму",
        roles=(UserRole.DOSING_OPERATOR,),
    )
