"""Бизнес-логика профиля кандидата."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.models.candidate import DEFAULT_PRIVACY, CandidateProfile
from app.providers.registry import get_llm
from app.schemas.candidate import CandidateProfileIn, PrivacyUpdateRequest
from app.services.resume import extract_text_from_pdf


class ProfileError(DomainError):
    """Ошибка профиля соискателя."""


async def get_profile(session: AsyncSession, user_id: str) -> CandidateProfile | None:
    result = await session.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def _get_or_create(session: AsyncSession, user_id: str) -> CandidateProfile:
    profile = await get_profile(session, user_id)
    if profile is None:
        profile = CandidateProfile(
            user_id=user_id,
            contacts={},
            stack=[],
            roles=[],
            soft_skills=[],
            privacy=dict(DEFAULT_PRIVACY),
        )
        session.add(profile)
        await session.flush()
    return profile


async def upsert_profile(session: AsyncSession, user_id: str, data: CandidateProfileIn) -> CandidateProfile:
    """Сохранение профиля, заполненного вручную по форме."""
    profile = await _get_or_create(session, user_id)

    profile.full_name = data.full_name
    profile.contacts = data.contacts.model_dump(mode="json", exclude_none=True)
    profile.specialization = data.specialization
    profile.grade = data.grade
    profile.experience_years = data.experience_years
    profile.stack = list(data.stack)
    profile.roles = list(data.roles)
    profile.soft_skills = list(data.soft_skills)
    profile.summary = data.summary
    profile.resume_source = "form"

    await session.commit()
    await session.refresh(profile)
    return profile


async def apply_resume_upload(
    session: AsyncSession, user_id: str, *, filename: str, data: bytes
) -> tuple[CandidateProfile, dict[str, Any], int]:
    """Загрузка PDF-резюме: извлечение текста → автораспознавание → слияние в профиль."""
    text = extract_text_from_pdf(data)  # поднимает ResumeError с понятным сообщением
    llm = get_llm()
    parsed = await llm.extract_resume(text)

    profile = await _get_or_create(session, user_id)

    if parsed.get("full_name"):
        profile.full_name = parsed["full_name"]

    contacts = dict(profile.contacts or {})
    for key, value in (parsed.get("contacts") or {}).items():
        if value:
            contacts[key] = value
    profile.contacts = contacts

    if parsed.get("stack"):
        profile.stack = list(parsed["stack"])
    if parsed.get("roles"):
        profile.roles = list(parsed["roles"])
    if parsed.get("soft_skills"):
        profile.soft_skills = list(parsed["soft_skills"])
    if parsed.get("grade"):
        profile.grade = parsed["grade"]
    if parsed.get("experience_years") is not None:
        profile.experience_years = parsed["experience_years"]

    profile.resume_source = "pdf_upload"
    profile.resume_filename = filename
    profile.raw_resume_text = text

    await session.commit()
    await session.refresh(profile)
    return profile, parsed, len(text)


async def update_privacy(
    session: AsyncSession, profile: CandidateProfile, payload: PrivacyUpdateRequest
) -> CandidateProfile:
    privacy = dict(profile.privacy or DEFAULT_PRIVACY)
    for field, value in payload.model_dump(exclude_none=True).items():
        privacy[field] = bool(value)
    # Флаги видимости (стек, опыт, достижения ФСП) применяются при выдаче кандидата
    # работодателю. Скрытие контактов обеспечивается отдельным правилом: контакты
    # раскрываются только после принятия приглашения или самостоятельного отклика.
    profile.privacy = privacy
    await session.commit()
    await session.refresh(profile)
    return profile


def pdf_payload(profile: CandidateProfile) -> dict[str, Any]:
    return {
        "full_name": profile.full_name,
        "contacts": profile.contacts or {},
        "specialization": profile.specialization,
        "grade": profile.grade,
        "experience_years": profile.experience_years,
        "stack": profile.stack or [],
        "roles": profile.roles or [],
        "soft_skills": profile.soft_skills or [],
        "summary": profile.summary,
        "privacy": profile.privacy or DEFAULT_PRIVACY,
    }
