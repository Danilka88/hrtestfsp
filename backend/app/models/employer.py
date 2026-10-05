"""Модели кабинета работодателя: компания, потребность, подборка."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base


class EmployerProfile(Base):
    __tablename__ = "employer_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class EmployerNeed(Base):
    """Описание потребности: на его основе формируется подборка."""

    __tablename__ = "employer_needs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    employer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("specializations.id", ondelete="SET NULL"), nullable=True
    )
    grade_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    stack: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    salary_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Selection(Base):
    """Сохранённая подборка.

    Подборки неизменяемы: уточнение запроса создаёт новую подборку со ссылкой на
    предыдущую (`parent_selection_id`), поэтому ранее полученный результат не теряется.
    """

    __tablename__ = "selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    employer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    need_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employer_needs.id", ondelete="SET NULL"), nullable=True
    )
    parent_selection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("selections.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class SelectionCandidate(Base):
    """Кандидат в подборке: позиция, балл и объяснение попадания (evidence-trail)."""

    __tablename__ = "selection_candidates"
    __table_args__ = (UniqueConstraint("selection_id", "candidate_user_id", name="uq_selection_candidate"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    selection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("selections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    missing: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
