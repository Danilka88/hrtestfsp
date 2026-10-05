"""Схемы ИИ-эндпоинтов.

Каждый ответ содержит признак источника: `degraded=true` означает, что модель
недоступна и отданы детерминированные демо-данные — интерфейс обязан показать
это, а не выдавать за работу модели.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AIStatusOut(BaseModel):
    provider: str = Field(description="Активный источник: ollama или demo")
    available: bool = Field(description="Доступна ли реальная модель")
    degraded: bool = Field(description="Работает ли система на демо-данных")
    model: str | None = Field(default=None, description="Имя используемой модели")
    base_url: str | None = None
    think: bool | None = Field(default=None, description="Включён ли режим рассуждений")
    detail: str | None = None
    hint: str = Field(description="Готовая формулировка для интерфейса")


class AIResultOut(BaseModel):
    data: dict[str, Any] = Field(description="Результат задачи")
    provider: str = Field(description="Кто сформировал ответ")
    degraded: bool = Field(description="Ответ сформирован демо-данными, а не моделью")
    latency_ms: int = Field(description="Сколько заняло выполнение")
    note: str | None = Field(default=None, description="Пояснение для пользователя")
    warnings: list[str] = Field(default_factory=list)


class ProfileAnalyzeIn(BaseModel):
    text: str = Field(min_length=20, max_length=20000, description="Текст резюме или описания профиля")


class NeedDraftIn(BaseModel):
    brief: str = Field(min_length=5, max_length=4000, description="Краткое описание потребности")


class InvitationDraftIn(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    candidate_grade: str | None = None
    stack: list[str] = Field(default_factory=list)
    salary_from: int = Field(ge=0)
    salary_to: int = Field(ge=0)
    role_title: str | None = None


class CoverLetterIn(BaseModel):
    vacancy_title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    required_stack: list[str] = Field(default_factory=list)
    candidate_stack: list[str] = Field(default_factory=list)
    candidate_grade: str | None = None


class MatchExplainIn(BaseModel):
    selection_id: str
    candidate_reference: str


class TaskDraftIn(BaseModel):
    need_title: str = Field(min_length=1, max_length=200)
    stack: list[str] = Field(default_factory=list)
    grade: str | None = None


class SemanticScoresIn(BaseModel):
    need_text: str = Field(min_length=3, max_length=4000)
    candidate_texts: list[str] = Field(min_length=1, max_length=100)
