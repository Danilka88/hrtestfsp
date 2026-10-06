"""Схемы профиля кандидата."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Contacts(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    telegram: str | None = Field(default=None, max_length=64)


class PrivacySettings(BaseModel):
    show_contacts: bool = False
    show_stack: bool = True
    show_experience: bool = True
    show_fsp: bool = True


class CandidateProfileIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    contacts: Contacts = Field(default_factory=Contacts)
    specialization: str | None = Field(default=None, max_length=120)
    declared_grade: str | None = Field(
        default=None,
        max_length=20,
        description=(
            "Заявленный грейд из формы или резюме. Подтверждённый грейд присваивает тест — "
            "самоописание в банк работодателя не попадает."
        ),
    )
    experience_years: int | None = Field(default=None, ge=0, le=60)
    stack: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    summary: str | None = Field(default=None, max_length=4000)


class CandidateProfileOut(CandidateProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    # Подтверждённый тестом грейд: только чтение, присваивается тестированием.
    grade: str | None = None
    resume_source: str
    resume_filename: str | None = None
    privacy: PrivacySettings
    created_at: datetime
    updated_at: datetime


class ParsedResume(BaseModel):
    """Результат автораспознавания резюме (данные провайдера, без додумывания)."""

    full_name: str | None = None
    contacts: dict[str, str | None] = Field(default_factory=dict)
    stack: list[str] = Field(default_factory=list)
    grade: str | None = None
    roles: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    soft_skills: list[str] = Field(default_factory=list)
    source: str = "mock"


class ResumeUploadResponse(BaseModel):
    profile: CandidateProfileOut
    parsed: ParsedResume
    text_chars: int
    message: str


class PrivacyUpdateRequest(BaseModel):
    show_contacts: bool | None = None
    show_stack: bool | None = None
    show_experience: bool | None = None
    show_fsp: bool | None = None
