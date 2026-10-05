"""Эндпоинты приглашений: сторона работодателя и сторона кандидата."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_session
from app.models.user import User, UserRole
from app.schemas.invitation import (
    InvitationCandidateView,
    InvitationCreate,
    InvitationDecision,
    InvitationEmployerView,
)
from app.services import invitations as invitation_service

router_employer = APIRouter(prefix="/employers/me/invitations", tags=["invitations:employer"])
router_candidate = APIRouter(prefix="/candidates/me/invitations", tags=["invitations:candidate"])

employer_only = require_roles(UserRole.EMPLOYER)
candidate_only = require_roles(UserRole.CANDIDATE)


@router_employer.post("", response_model=InvitationEmployerView,
                      summary="Направить приглашение конкретному кандидату")
async def send_invitation(
    payload: InvitationCreate,
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> InvitationEmployerView:
    invitation = await invitation_service.create_invitation(session, user.id, payload)
    view = await invitation_service.employer_view(session, invitation)
    return InvitationEmployerView.model_validate(view)


@router_employer.get("", response_model=List[InvitationEmployerView],
                     summary="Приглашения работодателя и их статусы")
async def list_invitations(
    user: User = Depends(employer_only),
    session: AsyncSession = Depends(get_session),
) -> List[InvitationEmployerView]:
    views = await invitation_service.list_for_employer(session, user.id)
    return [InvitationEmployerView.model_validate(v) for v in views]


@router_candidate.get("", response_model=List[InvitationCandidateView],
                      summary="Входящие приглашения кандидата")
async def my_invitations(
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> List[InvitationCandidateView]:
    views = await invitation_service.list_for_candidate(session, user.id)
    return [InvitationCandidateView.model_validate(v) for v in views]


@router_candidate.post("/{invitation_id}/view", response_model=InvitationCandidateView,
                       summary="Отметить приглашение просмотренным")
async def view_invitation(
    invitation_id: str,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> InvitationCandidateView:
    invitation = await invitation_service.mark_viewed(session, user.id, invitation_id)
    return InvitationCandidateView.model_validate(
        await invitation_service.candidate_view(session, invitation)
    )


@router_candidate.post("/{invitation_id}/decision", response_model=InvitationCandidateView,
                       summary="Принять или отклонить приглашение")
async def decide_invitation(
    invitation_id: str,
    payload: InvitationDecision,
    user: User = Depends(candidate_only),
    session: AsyncSession = Depends(get_session),
) -> InvitationCandidateView:
    if payload.status not in {"accepted", "declined"}:
        from app.services.invitations import InvitationError

        raise InvitationError(400, "Допустимые значения: accepted или declined")
    invitation = await invitation_service.decide(
        session, user.id, invitation_id, accept=payload.status == "accepted"
    )
    return InvitationCandidateView.model_validate(
        await invitation_service.candidate_view(session, invitation)
    )
