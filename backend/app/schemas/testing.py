"""Схемы тестирования и категоризации."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SpecializationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str


class GradeOut(BaseModel):
    code: str
    title: str
    rank_order: int


class SurveyRequest(BaseModel):
    industry: str = Field(default="it", max_length=64)
    specialization_code: str = Field(max_length=64)
    answers: Dict[str, Any] = Field(default_factory=dict)


class SurveyResponseOut(BaseModel):
    id: str
    industry: str
    specialization_code: str
    grade_options: List[str]
    created_at: datetime


class StartSessionRequest(BaseModel):
    specialization_code: str = Field(max_length=64)
    target_grade: str = Field(max_length=20, description="Грейд, на который тестируется кандидат")


class ItemOut(BaseModel):
    id: str
    skill_tag: str
    question: Optional[str] = None
    options: List[str] = Field(default_factory=list)


class StartSessionResponse(BaseModel):
    session_id: str
    target_grade: str
    item: ItemOut
    note: str


class AnswerRequest(BaseModel):
    item_id: str
    answer_index: int = Field(ge=0)
    response_time_ms: Optional[int] = Field(default=None, ge=0)


class GradeChangeOut(BaseModel):
    applied: bool
    reason: str


class SessionResultOut(BaseModel):
    session_id: str
    status: str
    items_answered: int
    theta: float
    standard_error: float
    converged: bool
    result_grade: str
    category_id: int
    specialization: Optional[str] = None
    current_grade: Optional[str] = None
    grade_change_applied: bool
    grade_change_reason: str
    warnings: List[str] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    correct: bool
    finished: bool
    next_item: Optional[ItemOut] = None
    result: Optional[SessionResultOut] = None


class GradeHistoryEntry(BaseModel):
    from_grade: Optional[str] = None
    to_grade: str
    at: datetime


class SessionSummary(BaseModel):
    id: str
    status: str
    target_grade: str
    result_grade: Optional[str] = None
    items_answered: int
    theta: float


class CategoryStatusOut(BaseModel):
    specialization: Optional[str] = None
    grade: Optional[str] = None
    grade_change_allowed: bool
    grade_change_available_in_days: Optional[int] = None
    grade_change_cooldown_days: int
    grade_options: List[str]
    grade_history: List[GradeHistoryEntry]
    sessions: List[SessionSummary]
