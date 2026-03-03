"""
RAG-цепочка: Retrieval & Generation через Grok API (xAI).

Подключается к существующей ChromaDB, ищет релевантные чанки
и генерирует ответ через Grok API (OpenAI-совместимый).

Все тяжёлые компоненты (эмбеддинги, ChromaDB) инициализируются
лениво — при первом вызове get_answer(), а не при импорте модуля.
"""

import logging
from pathlib import Path

from openai import AsyncOpenAI

from core.config import settings

logger = logging.getLogger(__name__)

# ── Пути и параметры ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "mes_docs"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# ── Модель Grok ─────────────────────────────────────────────────────────
GROK_MODEL = "grok-3-mini-fast"

# ── Системный промпт ────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "Ты опытный главный инженер завода. Твоя задача — ответить на вопрос "
    "пользователя, опираясь на предоставленные отрывки технической документации.\n"
    "Анализируй смысл текста, а не только точные совпадения слов.\n"
    "Если в тексте есть ответ по смыслу — перефразируй его понятно и дай ответ.\n"
    "Если информации ДЕЙСТВИТЕЛЬНО нет в предоставленном тексте, ответь: "
    "\"В технической документации нет информации по этому вопросу\"."
)

# ── Ленивая инициализация (не блокирует запуск бота) ─────────────────────
_retriever = None


def _get_retriever():
    """Создаёт retriever при первом вызове."""
    global _retriever
    if _retriever is None:
        logger.info("Инициализация RAG: загрузка эмбеддингов и ChromaDB...")
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_chroma import Chroma

        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME,
        )
        _retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
        logger.info("RAG инициализирован успешно.")
    return _retriever


def _get_grok_client() -> AsyncOpenAI:
    """Создаёт async-клиент для Grok API."""
    return AsyncOpenAI(
        api_key=settings.GROK_API_KEY,
        base_url="https://api.x.ai/v1",
    )


def _format_docs(docs: list) -> str:
    """Объединяет документы в один текстовый контекст."""
    texts = [doc.page_content for doc in docs]
    combined = "\n\n---\n\n".join(texts)
    logger.info(
        "Retriever нашёл %d чанков, общий размер контекста: %d символов",
        len(docs), len(combined),
    )
    return combined


async def get_answer(question: str) -> str:
    """
    Принимает вопрос пользователя, ищет в ChromaDB релевантные документы,
    генерирует ответ через Grok API и возвращает строку.
    """
    logger.info("RAG запрос: %s", question)

    # 1. Получаем релевантные документы из ChromaDB
    retriever = _get_retriever()
    docs = await retriever.ainvoke(question)
    context = _format_docs(docs)

    # 2. Формируем запрос к Grok API
    client = _get_grok_client()

    user_message = f"Контекст из документации:\n{context}\n\nВопрос: {question}"

    response = await client.chat.completions.create(
        model=GROK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.0,
        max_tokens=1024,
    )

    answer = response.choices[0].message.content or "(пустой ответ)"
    logger.info("RAG ответ: %s", answer[:200])
    return answer
