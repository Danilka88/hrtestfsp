"""Схемы кабинета работодателя."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmployerProfileIn(BaseModel):
    company_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    industry: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=320)


class EmployerProfileOut(EmployerProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class NeedIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    specialization_code: str | None = Field(default=None, max_length=64)
    grade: str | None = Field(default=None, max_length=20)
    stack: list[str] = Field(default_factory=list)
    salary_from: int | None = Field(default=None, ge=0, le=100_000_000)
    salary_to: int | None = Field(default=None, ge=0, le=100_000_000)


class NeedOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    specialization_code: str | None = None
    grade: str | None = None
    stack: list[str] = Field(default_factory=list)
    created_at: datetime


class ReasonOut(BaseModel):
    code: str
    text: str
    value: float
    contribution: float


class CandidateCardOut(BaseModel):
    """Карточка кандидата для работодателя.

    Контакты не раскрываются до принятия приглашения или отклика кандидата,
    поэтому поля контактов здесь отсутствуют по построению.
    """

    reference: str
    full_name: str | None = None
    specialization: str | None = None
    grade: str | None = None
    category_id: int | None = None
    stack: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    fsp_achievements: int | None = None
    summary: str | None = None
    contacts_visible: bool = False
    rank: int
    score: float
    reasons: list[ReasonOut] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class SelectionOut(BaseModel):
    id: str
    title: str
    need_id: str | None = None
    parent_selection_id: str | None = None
    rubric_version: str
    params: dict[str, Any] = Field(default_factory=dict)
    recommended_categories: list[int] = Field(default_factory=list)
    candidates: list[CandidateCardOut] = Field(default_factory=list)
    created_at: datetime


class SelectionSummaryOut(BaseModel):
    id: str
    title: str
    parent_selection_id: str | None = None
    candidates_count: int
    created_at: datetime


class SearchQuery(BaseModel):
    specialization_code: str | None = None
    grade: str | None = None
    category_id: int | None = None
    stack: list[str] = Field(default_factory=list)
    has_fsp: bool | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResultOut(BaseModel):
    total: int
    limit: int
    offset: int
    candidates: list[CandidateCardOut] = Field(default_factory=list)
