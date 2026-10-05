"""Схемы вакансий, откликов и регулярных коротких заданий."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VacancyIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=6000)
    specialization_code: str | None = Field(default=None, max_length=64)
    grade: str | None = Field(default=None, max_length=20)
    stack: list[str] = Field(default_factory=list)
    salary_from: int = Field(ge=0, le=100_000_000)
    salary_to: int = Field(ge=0, le=100_000_000)


class VacancyOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    specialization_code: str | None = None
    grade: str | None = None
    stack: list[str] = Field(default_factory=list)
    salary_from: int
    salary_to: int
    status: str
    company_name: str | None = None
    created_at: datetime


class ApplicationIn(BaseModel):
    message: str | None = Field(default=None, max_length=4000)


class ApplicationDecision(BaseModel):
    status: str = Field(description="accepted или declined")


class ContactsOut(BaseModel):
    email: str | None = None
    phone: str | None = None
    telegram: str | None = None


class ApplicationCandidateOut(BaseModel):
    id: str
    vacancy_id: str
    vacancy_title: str | None = None
    company_name: str | None = None
    message: str | None = None
    status: str
    created_at: datetime
    viewed_at: datetime | None = None
    decided_at: datetime | None = None


class ApplicationEmployerOut(BaseModel):
    """Отклик для работодателя: кандидат проявил инициативу сам, поэтому контакты открыты."""

    id: str
    vacancy_id: str
    candidate_reference: str
    candidate_name: str | None = None
    candidate_specialization: str | None = None
    candidate_grade: str | None = None
    candidate_stack: list[str] = Field(default_factory=list)
    message: str | None = None
    status: str
    created_at: datetime
    viewed_at: datetime | None = None
    decided_at: datetime | None = None
    candidate_contacts: ContactsOut | None = None
    contacts_revealed: bool = True


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=6000)
    specialization_code: str | None = Field(default=None, max_length=64)
    grade: str | None = Field(default=None, max_length=20)


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    specialization_code: str | None = None
    grade: str | None = None
    status: str
    company_name: str | None = None
    created_at: datetime


class SubmissionIn(BaseModel):
    solution: str = Field(min_length=1, max_length=20000)


class SubmissionOut(BaseModel):
    id: str
    task_id: str
    candidate_reference: str | None = None
    candidate_name: str | None = None
    candidate_specialization: str | None = None
    candidate_grade: str | None = None
    solution: str
    status: str
    created_at: datetime
