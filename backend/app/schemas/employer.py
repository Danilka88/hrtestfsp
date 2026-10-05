"""Схемы кабинета работодателя."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployerProfileIn(BaseModel):
    company_name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    industry: Optional[str] = Field(default=None, max_length=64)
    website: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[str] = Field(default=None, max_length=320)


class EmployerProfileOut(EmployerProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class NeedIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    specialization_code: Optional[str] = Field(default=None, max_length=64)
    grade: Optional[str] = Field(default=None, max_length=20)
    stack: List[str] = Field(default_factory=list)
    salary_from: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    salary_to: Optional[int] = Field(default=None, ge=0, le=100_000_000)


class NeedOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    specialization_code: Optional[str] = None
    grade: Optional[str] = None
    stack: List[str] = Field(default_factory=list)
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
    full_name: Optional[str] = None
    specialization: Optional[str] = None
    grade: Optional[str] = None
    category_id: Optional[int] = None
    stack: List[str] = Field(default_factory=list)
    experience_years: Optional[int] = None
    fsp_achievements: Optional[int] = None
    summary: Optional[str] = None
    contacts_visible: bool = False
    rank: int
    score: float
    reasons: List[ReasonOut] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)


class SelectionOut(BaseModel):
    id: str
    title: str
    need_id: Optional[str] = None
    parent_selection_id: Optional[str] = None
    rubric_version: str
    params: Dict[str, Any] = Field(default_factory=dict)
    recommended_categories: List[int] = Field(default_factory=list)
    candidates: List[CandidateCardOut] = Field(default_factory=list)
    created_at: datetime


class SelectionSummaryOut(BaseModel):
    id: str
    title: str
    parent_selection_id: Optional[str] = None
    candidates_count: int
    created_at: datetime


class SearchQuery(BaseModel):
    specialization_code: Optional[str] = None
    grade: Optional[str] = None
    category_id: Optional[int] = None
    stack: List[str] = Field(default_factory=list)
    has_fsp: Optional[bool] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SearchResultOut(BaseModel):
    total: int
    limit: int
    offset: int
    candidates: List[CandidateCardOut] = Field(default_factory=list)
