"""Модели тестирования: справочники, банк заданий, сессии, история грейдов."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base

SESSION_IN_PROGRESS = "in_progress"
SESSION_COMPLETED = "completed"
SESSION_ABANDONED = "abandoned"


class Specialization(Base):
    """Справочник специализаций (составляется командой)."""

    __tablename__ = "specializations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), default="it", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Grade(Base):
    """Справочник грейдов."""

    __tablename__ = "grades"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)


class Category(Base):
    """Категория = специализация × грейд. Именно её видит работодатель."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("specialization_id", "grade_code", name="uq_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specializations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("grades.code", ondelete="CASCADE"), nullable=False, index=True
    )


class Item(Base):
    """Задание банка.

    Сложность задаётся параметром `difficulty`, а формулировка — шаблоном из
    `payload`. Это позволяет генерировать уникальные варианты с сопоставимой
    сложностью и контролировать показы (`max_exposure`).
    """

    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    specialization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("specializations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(24), default="single_choice", nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    discrimination: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # payload описывает задание: текст вопроса, варианты ответа, индекс верного,
    # имя шаблона и параметры генерации (см. services/item_factory.py)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_exposure: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    exposure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SurveyResponse(Base):
    """Ответы опроса по отрасли и специализации (обязательный путь при регистрации)."""

    __tablename__ = "survey_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    specialization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specializations.id", ondelete="CASCADE"), nullable=False
    )
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class TestSession(Base):
    """Сессия прохождения теста: адаптивная выдача и оценка способности."""

    __tablename__ = "test_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    specialization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specializations.id", ondelete="CASCADE"), nullable=False
    )
    target_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=SESSION_IN_PROGRESS, nullable=False)

    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    theta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    standard_error: Mapped[float] = mapped_column(Float, default=99.0, nullable=False)
    result_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    # Задание, которое предъявлено кандидату и ещё не отвечено. Нужно, чтобы после
    # перерыва вернуть ровно его, а не подбирать заново (подбор зависит от счётчика
    # показов и после перерыва выдал бы другой вопрос).
    pending_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    grade_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ItemResponseRecord(Base):
    __tablename__ = "item_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answer: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class GradeChange(Base):
    """История смены грейда — основа ограничения частоты смены."""

    __tablename__ = "grade_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
