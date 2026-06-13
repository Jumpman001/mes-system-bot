"""
Единые обработчики ошибок для FastAPI.

Раньше каждый роут оборачивал тело в одинаковый
try/except SQLAlchemyError / except Exception. Теперь это вынесено сюда:
роуты просто выполняют свою работу, а ошибки БД и непредвиденные исключения
ловятся централизованно и превращаются в аккуратный JSON-ответ.

HTTPException (404, 400 и т.п.) обрабатывается встроенным механизмом FastAPI
и сюда не попадает.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует общие обработчики на переданном приложении."""

    @app.exception_handler(SQLAlchemyError)
    async def _sqlalchemy_error(request: Request, exc: SQLAlchemyError):
        logger.error("Ошибка БД на %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Ошибка базы данных."},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception):
        logger.exception(
            "Непредвиденная ошибка на %s %s: %s",
            request.method, request.url.path, exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Внутренняя ошибка сервера."},
        )
