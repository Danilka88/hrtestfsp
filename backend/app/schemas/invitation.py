"""Схемы приглашений и связи с ФСП."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class InvitationCreate(BaseModel):
    candidate_reference: str = Field(
        description="Ссылка кандидата из подборки или поиска, например cand-8049f321"
    )
    message: Optional[str] = Field(default=None, max_length=4000)
    salary_from: int = Field(ge=0, le=100_000_000, description="Обязательно")
    salary_to: int = Field(ge=0, le=100_000_000, description="Обязательно")
    contact_method: Optional[str] = Field(default=None, max_length=255)
    need_id: Optional[str] = None
    selection_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate_salary(self) -> "InvitationCreate":
        if self.salary_from > self.salary_to:
            raise ValueError("Нижняя граница зарплаты больше верхней")
        return self


class ContactsOut(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None


class InvitationEmployerView(BaseModel):
    """Представление приглашения для работодателя."""

    id: str
    candidate_reference: str
    candidate_name: Optional[str] = None
    candidate_specialization: Optional[str] = None
    candidate_grade: Optional[str] = None
    message: Optional[str] = None
    salary_from: int
    salary_to: int
    contact_method: Optional[str] = None
    status: str
    created_at: datetime
    viewed_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    # Раскрываются только после принятия приглашения кандидатом
    candidate_contacts: Optional[ContactsOut] = None
    contacts_revealed: bool = False


class InvitationCandidateView(BaseModel):
    """Представление приглашения для кандидата: условия видны до начала общения."""

    id: str
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    message: Optional[str] = None
    salary_from: int
    salary_to: int
    contact_method: Optional[str] = None
    status: str
    created_at: datetime
    viewed_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None


class InvitationDecision(BaseModel):
    status: str = Field(description="accepted или declined")


class FspLinkRequest(BaseModel):
    fsp_id: Optional[str] = Field(
        default=None, max_length=64, description="Идентификатор участника ФСП; null — отвязать"
    )


class FspAchievementOut(BaseModel):
    contest: str
    category: str
    year: int
    place: Optional[int] = None
    rating: Optional[float] = None


class FspStatusOut(BaseModel):
    fsp_id: Optional[str] = None
    linked: bool
    achievements: List[FspAchievementOut] = Field(default_factory=list)
    note: str
