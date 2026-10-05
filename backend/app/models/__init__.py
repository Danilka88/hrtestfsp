"""ORM-модели домена.

Импорт этого модуля наполняет `Base.metadata` — используется Alembic.
"""

from app.models.candidate import CandidateProfile
from app.models.user import EmailVerificationToken, RefreshToken, User

__all__ = ["User", "EmailVerificationToken", "RefreshToken", "CandidateProfile"]
