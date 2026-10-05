"""ORM-модели домена.

Импорт этого модуля наполняет `Base.metadata` — используется Alembic.
"""

from app.models.candidate import CandidateProfile
from app.models.employer import EmployerNeed, EmployerProfile, Selection, SelectionCandidate
from app.models.testing import (
    Category,
    Grade,
    GradeChange,
    Item,
    ItemResponseRecord,
    Specialization,
    SurveyResponse,
    TestSession,
)
from app.models.user import EmailVerificationToken, RefreshToken, User

__all__ = [
    "User",
    "EmailVerificationToken",
    "RefreshToken",
    "CandidateProfile",
    "Specialization",
    "Grade",
    "Category",
    "Item",
    "SurveyResponse",
    "TestSession",
    "ItemResponseRecord",
    "GradeChange",
    "EmployerProfile",
    "EmployerNeed",
    "Selection",
    "SelectionCandidate",
]
