"""
Хэндлер AI-ассистента — команда /ask для вопросов по документации.
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ai_agent.rag_chain import get_answer

router = Router(name="ai_assistant")
logger = logging.getLogger(__name__)


@router.message(Command("ask"))
async def cmd_ask(message: Message, command: CommandObject) -> None:
    """Обработчик команды /ask <вопрос>."""

    question = command.args

    if not question:
        await message.answer(
            "🤖 <b>AI-ассистент по документации</b>\n\n"
            "Напишите вопрос после команды, например:\n"
            "<code>/ask Какая вязкость у смолы?</code>",
            parse_mode="HTML",
        )
        return

    # Уведомляем, что ищем ответ
    wait_msg = await message.answer("⏳ Ищу в регламентах...")

    try:
        answer = await get_answer(question)
        await wait_msg.edit_text(
            f"🤖 <b>Ответ AI-ассистента:</b>\n\n{answer}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Ошибка RAG-цепочки: %s", e, exc_info=True)
        await wait_msg.edit_text(
            "❌ Произошла ошибка при обработке запроса. Попробуйте позже.",
        )
