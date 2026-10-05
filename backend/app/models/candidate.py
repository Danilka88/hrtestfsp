"""Модель профиля кандидата."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base

# Настройки приватности по умолчанию: контакты скрыты, остальное видно.
DEFAULT_PRIVACY: dict[str, bool] = {
    "show_contacts": False,
    "show_stack": True,
    "show_experience": True,
    "show_fsp": True,
}


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )

    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stack: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    soft_skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Источник профиля: "form" (заполнен вручную) или "pdf_upload" (распознан из резюме)
    resume_source: Mapped[str] = mapped_column(String(16), default="form", nullable=False)
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    privacy: Mapped[dict[str, bool]] = mapped_column(
        JSON, default=lambda: dict(DEFAULT_PRIVACY), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
