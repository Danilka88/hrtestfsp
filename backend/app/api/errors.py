"""Обработчики доменных ошибок.

Все доменные исключения наследуют `DomainError`, поэтому обработчик регистрируется
один раз на базовый класс. Новое исключение достаточно унаследовать — оно уже не
превратится в 500, и помнить про отдельную регистрацию не нужно. Это и было целью:
раньше список типов приходилось поддерживать вручную, и забытый тип давал ошибку
сервера вместо понятного ответа.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import DomainError


async def _domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Обработчик зарегистрирован на базовый класс, поэтому сюда попадают только его
    # наследники; проверка оставлена на случай ошибочной регистрации.
    if not isinstance(exc, DomainError):
        return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервиса"})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_domain_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
