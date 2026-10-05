"""Модель приглашения работодателя кандидату.

Ключевая механика продукта: инициатива у работодателя, приглашение не привязано
обязательно к опубликованной вакансии, а контакты кандидата раскрываются только
после принятия приглашения.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import utcnow
from app.db.base import Base

STATUS_SENT = "sent"
STATUS_VIEWED = "viewed"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
# Работодатель может отозвать приглашение, пока кандидат не принял решение:
# отправленное по ошибке предложение не должно висеть на кандидате.
STATUS_REVOKED = "revoked"

ALL_STATUSES = (STATUS_SENT, STATUS_VIEWED, STATUS_ACCEPTED, STATUS_DECLINED, STATUS_REVOKED)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    employer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    need_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employer_needs.id", ondelete="SET NULL"), nullable=True
    )
    selection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("selections.id", ondelete="SET NULL"), nullable=True
    )
    # Вакансия появится в дополнительном функционале (Этап 6) — привязка необязательна
    vacancy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Зарплата обязательна: кандидат видит условия до начала общения
    salary_from: Mapped[int] = mapped_column(Integer, nullable=False)
    salary_to: Mapped[int] = mapped_column(Integer, nullable=False)
    contact_method: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default=STATUS_SENT, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
