"""Обработчики доменных ошибок.

Доменные исключения несут HTTP-код и сообщение. Регистрация одного обработчика
на все типы гарантирует, что они не превращаются в 500 при новых эндпоинтах —
это устраняет целый класс ошибок «забыл обернуть вызов».
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.auth import AuthError
from app.services.candidates import ProfileError
from app.services.employers import EmployerError
from app.services.invitations import InvitationError
from app.services.marketplace import MarketplaceError
from app.services.resume import ResumeError
from app.services.testing_flow import TestingError

DOMAIN_ERRORS = (
    AuthError,
    ProfileError,
    ResumeError,
    EmployerError,
    InvitationError,
    MarketplaceError,
    TestingError,
)


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = getattr(exc, "status_code", 400)
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=status_code, content={"detail": detail})


def register_domain_error_handlers(app: FastAPI) -> None:
    for error_type in DOMAIN_ERRORS:
        app.add_exception_handler(error_type, _domain_error_handler)
