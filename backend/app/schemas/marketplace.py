"""Схемы вакансий, откликов и регулярных коротких заданий."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class VacancyIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=6000)
    specialization_code: Optional[str] = Field(default=None, max_length=64)
    grade: Optional[str] = Field(default=None, max_length=20)
    stack: List[str] = Field(default_factory=list)
    salary_from: int = Field(ge=0, le=100_000_000)
    salary_to: int = Field(ge=0, le=100_000_000)


class VacancyOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    specialization_code: Optional[str] = None
    grade: Optional[str] = None
    stack: List[str] = Field(default_factory=list)
    salary_from: int
    salary_to: int
    status: str
    company_name: Optional[str] = None
    created_at: datetime


class ApplicationIn(BaseModel):
    message: Optional[str] = Field(default=None, max_length=4000)


class ApplicationDecision(BaseModel):
    status: str = Field(description="accepted или declined")


class ContactsOut(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None


class ApplicationCandidateOut(BaseModel):
    id: str
    vacancy_id: str
    vacancy_title: Optional[str] = None
    company_name: Optional[str] = None
    message: Optional[str] = None
    status: str
    created_at: datetime
    viewed_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None


class ApplicationEmployerOut(BaseModel):
    """Отклик для работодателя: кандидат проявил инициативу сам, поэтому контакты открыты."""

    id: str
    vacancy_id: str
    candidate_reference: str
    candidate_name: Optional[str] = None
    candidate_specialization: Optional[str] = None
    candidate_grade: Optional[str] = None
    candidate_stack: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    status: str
    created_at: datetime
    viewed_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    candidate_contacts: Optional[ContactsOut] = None
    contacts_revealed: bool = True


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=6000)
    specialization_code: Optional[str] = Field(default=None, max_length=64)
    grade: Optional[str] = Field(default=None, max_length=20)


class TaskOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    specialization_code: Optional[str] = None
    grade: Optional[str] = None
    status: str
    company_name: Optional[str] = None
    created_at: datetime


class SubmissionIn(BaseModel):
    solution: str = Field(min_length=1, max_length=20000)


class SubmissionOut(BaseModel):
    id: str
    task_id: str
    candidate_reference: Optional[str] = None
    candidate_name: Optional[str] = None
    candidate_specialization: Optional[str] = None
    candidate_grade: Optional[str] = None
    solution: str
    status: str
    created_at: datetime
