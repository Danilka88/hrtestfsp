"""Базовый класс декларативных моделей.

Модели домена (User, CandidateProfile, TestSession, ...) добавляются на
последующих этапах и наследуются от `Base`.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Общий declarative base для всех ORM-моделей."""
