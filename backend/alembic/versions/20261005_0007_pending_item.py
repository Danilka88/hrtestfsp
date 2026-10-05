"""test_sessions.pending_item_id: предъявленное и ещё не отвеченное задание

Нужен, чтобы после перерыва кандидат получил ровно то задание, которое видел:
подбор следующего задания зависит от счётчика показов, поэтому повторный расчёт
после перерыва выдал бы другой вопрос.

Revision ID: 20261005_0007
Revises: 20261005_0006
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261005_0007"
down_revision: str | None = "20261005_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("test_sessions", sa.Column("pending_item_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("test_sessions", "pending_item_id")
