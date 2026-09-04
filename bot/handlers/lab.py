"""
Хэндлер Лаборанта — команда /lab открывает форму лабораторных тестов.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards import open_webapp
from db.models import UserRole

router = Router(name="lab")


@router.message(Command("lab"))
async def cmd_lab(message: Message) -> None:
    """Кнопка Mini App для ввода результатов лабораторных тестов."""
    await open_webapp(
        message,
        path="/lab",
        title="🔬 Лабораторные тесты",
        description="Внесите время гелеобразования или результат теста песка.",
        button="Открыть форму",
        roles=(UserRole.LAB_TECHNICIAN,),
    )
