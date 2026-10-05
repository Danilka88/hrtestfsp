"""Дополнительный функционал: вакансии, отклики, регулярные короткие задания.

Эти сценарии не обязательны для MVP, но дают кандидату возможность проявить
инициативу, пока приглашений нет, и поддерживают профиль в актуальном состоянии.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base

VACANCY_PUBLISHED = "published"
VACANCY_CLOSED = "closed"

APPLICATION_SENT = "sent"
APPLICATION_VIEWED = "viewed"
APPLICATION_ACCEPTED = "accepted"
APPLICATION_DECLINED = "declined"

TASK_OPEN = "open"
TASK_CLOSED = "closed"

SUBMISSION_NEW = "submitted"
SUBMISSION_REVIEWED = "reviewed"


class Vacancy(Base):
    __tablename__ = "vacancies"

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
    stack: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Зарплата в вакансии обязательна
    salary_from: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_to: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=VACANCY_PUBLISHED, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Application(Base):
    """Отклик кандидата на вакансию — самостоятельная инициатива кандидата.

    Такой отклик, как и принятое приглашение, раскрывает работодателю контакты.
    """

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    vacancy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=APPLICATION_SENT, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RegularTask(Base):
    """Короткое задание работодателя: решить или предложить подход."""

    __tablename__ = "regular_tasks"

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
    status: Mapped[str] = mapped_column(String(16), default=TASK_OPEN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class TaskSubmission(Base):
    """Решение кандидата (или предложенный подход).

    Участие в регулярных заданиях — сигнал свежести профиля для работодателя.
    """

    __tablename__ = "task_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("regular_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=SUBMISSION_NEW, nullable=False)
    employer_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
