"""Схемы приглашений и связи с ФСП."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class InvitationCreate(BaseModel):
    candidate_reference: str = Field(
        description="Ссылка кандидата из подборки или поиска, например cand-8049f321"
    )
    message: str | None = Field(default=None, max_length=4000)
    salary_from: int = Field(ge=0, le=100_000_000, description="Обязательно")
    salary_to: int = Field(ge=0, le=100_000_000, description="Обязательно")
    contact_method: str | None = Field(default=None, max_length=255)
    need_id: str | None = None
    selection_id: str | None = None

    @model_validator(mode="after")
    def _validate_salary(self) -> InvitationCreate:
        if self.salary_from > self.salary_to:
            raise ValueError("Нижняя граница зарплаты больше верхней")
        return self


class ContactsOut(BaseModel):
    email: str | None = None
    phone: str | None = None
    telegram: str | None = None


class InvitationEmployerView(BaseModel):
    """Представление приглашения для работодателя."""

    id: str
    candidate_reference: str
    candidate_name: str | None = None
    candidate_specialization: str | None = None
    candidate_grade: str | None = None
    message: str | None = None
    salary_from: int
    salary_to: int
    contact_method: str | None = None
    status: str
    created_at: datetime
    viewed_at: datetime | None = None
    decided_at: datetime | None = None
    # Раскрываются только после принятия приглашения кандидатом
    candidate_contacts: ContactsOut | None = None
    contacts_revealed: bool = False


class InvitationCandidateView(BaseModel):
    """Представление приглашения для кандидата: условия видны до начала общения."""

    id: str
    company_name: str | None = None
    company_description: str | None = None
    message: str | None = None
    salary_from: int
    salary_to: int
    contact_method: str | None = None
    status: str
    created_at: datetime
    viewed_at: datetime | None = None
    decided_at: datetime | None = None


class InvitationDecision(BaseModel):
    status: str = Field(description="accepted или declined")


class FspLinkRequest(BaseModel):
    fsp_id: str | None = Field(
        default=None, max_length=64, description="Идентификатор участника ФСП; null — отвязать"
    )


class FspAchievementOut(BaseModel):
    contest: str
    category: str
    year: int
    place: int | None = None
    rating: float | None = None


class FspStatusOut(BaseModel):
    fsp_id: str | None = None
    linked: bool
    achievements: list[FspAchievementOut] = Field(default_factory=list)
    note: str
