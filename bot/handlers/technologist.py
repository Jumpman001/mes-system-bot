"""
Хэндлер Технолога — команда /dry_materials открывает форму сухих материалов.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import open_webapp
from db.models import UserRole

router = Router(name="technologist")


@router.message(Command("dry_materials"))
async def cmd_dry_materials(message: Message) -> None:
    """Кнопка Mini App для ввода расхода сухих материалов."""
    await open_webapp(
        message,
        path="/dry_materials",
        title="🧵 Сухие материалы",
        description="Внесите фактический расход стекловолокна, песка, марли и лент.",
        button="Открыть форму",
        roles=(UserRole.TECHNOLOGIST,),
    )
