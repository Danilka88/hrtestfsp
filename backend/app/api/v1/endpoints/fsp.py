"""Эндпоинты связи профиля кандидата с идентификатором участника ФСП."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.invitation import FspLinkRequest, FspStatusOut
from app.services import fsp_link

router = APIRouter(prefix="/candidates/me/fsp", tags=["fsp"])

candidate_only = require_roles(UserRole.CANDIDATE)


@router.get("", response_model=FspStatusOut, summary="Состояние связи с ФСП и достижения")
async def get_status(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> FspStatusOut:
    return FspStatusOut.model_validate(await fsp_link.status(session, user))


@router.put("", response_model=FspStatusOut, summary="Привязать или отвязать идентификатор ФСП")
async def link(
    payload: FspLinkRequest,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> FspStatusOut:
    await fsp_link.link(session, user, payload.fsp_id)
    return FspStatusOut.model_validate(await fsp_link.status(session, user))
