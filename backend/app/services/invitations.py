"""Приглашения: создание, статусы, раскрытие контактов, решения кандидата.

Раскрытие контактов кандидата — не «настройка отображения», а следствие статуса:
работодатель получает контакты только после принятия приглашения.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.security import utcnow
from app.models.candidate import CandidateProfile
from app.models.employer import EmployerProfile
from app.models.invitation import (
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_REVOKED,
    STATUS_SENT,
    STATUS_VIEWED,
    Invitation,
)
from app.models.user import User, UserRole
from app.schemas.invitation import InvitationCreate
from app.services.reference import (
    CANDIDATE_REFERENCE_PREFIX,
    SPECIALIZATIONS,  # noqa: F401  (единый справочник)
    candidate_reference,
)

logger = logging.getLogger(__name__)


class InvitationError(DomainError):
    """Ошибка приглашения: статус, доступ, повторная отправка."""


async def resolve_candidate_reference(session: AsyncSession, reference: str) -> User:
    """Находит кандидата по ссылке из подборки/поиска (например cand-8049f321)."""
    raw = (reference or "").strip()
    prefix = raw[len(CANDIDATE_REFERENCE_PREFIX) :] if raw.startswith(CANDIDATE_REFERENCE_PREFIX) else raw
    if len(prefix) < 6:
        raise InvitationError(400, "Некорректная ссылка кандидата")

    rows = list(
        (
            await session.execute(
                select(User).where(
                    User.role == UserRole.CANDIDATE, User.id.like(f"{prefix}%"), User.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise InvitationError(404, "Кандидат не найден")
    if len(rows) > 1:
        raise InvitationError(409, "Ссылка кандидата неоднозначна — уточните выбор")
    return rows[0]


async def create_invitation(session: AsyncSession, employer_id: str, payload: InvitationCreate) -> Invitation:
    candidate = await resolve_candidate_reference(session, payload.candidate_reference)

    duplicate = (
        await session.execute(
            select(Invitation).where(
                Invitation.employer_id == employer_id,
                Invitation.candidate_user_id == candidate.id,
                Invitation.status.in_([STATUS_SENT, STATUS_VIEWED, STATUS_ACCEPTED]),
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise InvitationError(409, "Активное приглашение этому кандидату уже отправлено")

    invitation = Invitation(
        employer_id=employer_id,
        candidate_user_id=candidate.id,
        need_id=payload.need_id,
        selection_id=payload.selection_id,
        message=payload.message,
        salary_from=payload.salary_from,
        salary_to=payload.salary_to,
        contact_method=payload.contact_method,
        status=STATUS_SENT,
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation


async def _candidate_context(
    session: AsyncSession, candidate_user_id: str
) -> tuple[CandidateProfile | None, User | None]:
    profile = (
        await session.execute(select(CandidateProfile).where(CandidateProfile.user_id == candidate_user_id))
    ).scalar_one_or_none()
    user = await session.get(User, candidate_user_id)
    return profile, user


async def employer_view(session: AsyncSession, invitation: Invitation) -> dict[str, Any]:
    profile, user = await _candidate_context(session, invitation.candidate_user_id)
    revealed = invitation.status == STATUS_ACCEPTED

    contacts = None
    if revealed and profile is not None:
        raw_contacts = profile.contacts or {}
        contacts = {
            "email": raw_contacts.get("email"),
            "phone": raw_contacts.get("phone"),
            "telegram": raw_contacts.get("telegram"),
        }

    return {
        "id": invitation.id,
        "candidate_reference": candidate_reference(invitation.candidate_user_id),
        "candidate_name": profile.full_name if profile is not None else None,
        "candidate_specialization": profile.specialization if profile is not None else None,
        "candidate_grade": profile.grade if profile is not None else None,
        "message": invitation.message,
        "salary_from": invitation.salary_from,
        "salary_to": invitation.salary_to,
        "contact_method": invitation.contact_method,
        "status": invitation.status,
        "created_at": invitation.created_at,
        "viewed_at": invitation.viewed_at,
        "decided_at": invitation.decided_at,
        "candidate_contacts": contacts,
        "contacts_revealed": revealed,
        "can_revoke": invitation.status in (STATUS_SENT, STATUS_VIEWED),
    }


async def candidate_view(session: AsyncSession, invitation: Invitation) -> dict[str, Any]:
    company = (
        await session.execute(
            select(EmployerProfile).where(EmployerProfile.user_id == invitation.employer_id)
        )
    ).scalar_one_or_none()
    return {
        "id": invitation.id,
        "company_name": company.company_name if company is not None else None,
        "company_description": company.description if company is not None else None,
        "message": invitation.message,
        "salary_from": invitation.salary_from,
        "salary_to": invitation.salary_to,
        "contact_method": invitation.contact_method,
        "status": invitation.status,
        "created_at": invitation.created_at,
        "viewed_at": invitation.viewed_at,
        "decided_at": invitation.decided_at,
    }


async def list_for_employer(session: AsyncSession, employer_id: str) -> list[dict[str, Any]]:
    invitations = list(
        (
            await session.execute(
                select(Invitation)
                .where(Invitation.employer_id == employer_id)
                .order_by(Invitation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await employer_view(session, item) for item in invitations]


async def list_for_candidate(session: AsyncSession, candidate_user_id: str) -> list[dict[str, Any]]:
    invitations = list(
        (
            await session.execute(
                select(Invitation)
                .where(Invitation.candidate_user_id == candidate_user_id)
                .order_by(Invitation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await candidate_view(session, item) for item in invitations]


async def _get_own_invitation(
    session: AsyncSession, candidate_user_id: str, invitation_id: str
) -> Invitation:
    invitation = await session.get(Invitation, invitation_id)
    if invitation is None or invitation.candidate_user_id != candidate_user_id:
        # Одинаковый ответ, чтобы не раскрывать существование чужих записей
        raise InvitationError(404, "Приглашение не найдено")
    return invitation


async def mark_viewed(session: AsyncSession, candidate_user_id: str, invitation_id: str) -> Invitation:
    invitation = await _get_own_invitation(session, candidate_user_id, invitation_id)
    if invitation.status == STATUS_SENT:
        invitation.status = STATUS_VIEWED
        invitation.viewed_at = utcnow()
        await session.commit()
        await session.refresh(invitation)
    return invitation


async def revoke(session: AsyncSession, employer_id: str, invitation_id: str) -> Invitation:
    """Отзывает приглашение. Решение кандидата отменить нельзя — это история."""
    invitation = await session.get(Invitation, invitation_id)
    if invitation is None or invitation.employer_id != employer_id:
        # Одинаковый ответ, чтобы не раскрывать существование чужих записей
        raise InvitationError(404, "Приглашение не найдено")
    if invitation.status in (STATUS_ACCEPTED, STATUS_DECLINED):
        raise InvitationError(409, "По приглашению уже принято решение — отозвать его нельзя")
    if invitation.status == STATUS_REVOKED:
        raise InvitationError(409, "Приглашение уже отозвано")
    invitation.status = STATUS_REVOKED
    invitation.decided_at = utcnow()
    await session.commit()
    await session.refresh(invitation)
    return invitation


async def decide(
    session: AsyncSession, candidate_user_id: str, invitation_id: str, *, accept: bool
) -> Invitation:
    invitation = await _get_own_invitation(session, candidate_user_id, invitation_id)
    if invitation.status == STATUS_REVOKED:
        raise InvitationError(409, "Работодатель отозвал приглашение")
    if invitation.status in (STATUS_ACCEPTED, STATUS_DECLINED):
        raise InvitationError(409, "Решение по приглашению уже принято")

    invitation.status = STATUS_ACCEPTED if accept else STATUS_DECLINED
    invitation.decided_at = utcnow()
    if invitation.viewed_at is None:
        invitation.viewed_at = invitation.decided_at
    await session.commit()
    await session.refresh(invitation)
    return invitation
