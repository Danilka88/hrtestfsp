"""candidate_profiles.declared_grade: заявленный грейд отдельно от подтверждённого

Грейд, который кандидат указал в форме или в резюме, — это самоописание. Раньше он
писался в ту же колонку `grade`, что и результат теста, и кандидат, не проходивший
тест, попадал в банк работодателя как «подтверждённый» (банк отбирает по
`grade IS NOT NULL`). Теперь самоописание живёт в `declared_grade`, а `grade`
присваивает только тест.

Revision ID: 20261005_0008
Revises: 20261005_0007
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261005_0008"
down_revision: str | None = "20261005_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles", sa.Column("declared_grade", sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "declared_grade")
