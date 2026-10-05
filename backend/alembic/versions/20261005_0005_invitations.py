"""invitations

Revision ID: 20261005_0005
Revises: 20261005_0004
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0005"
down_revision: Union[str, None] = "20261005_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employer_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_user_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("need_id", sa.String(length=36),
                  sa.ForeignKey("employer_needs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("selection_id", sa.String(length=36),
                  sa.ForeignKey("selections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("vacancy_id", sa.String(length=36), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("contact_method", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="sent"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_invitations_employer_id", "invitations", ["employer_id"])
    op.create_index("ix_invitations_candidate_user_id", "invitations", ["candidate_user_id"])
    op.create_index("ix_invitations_status", "invitations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_invitations_status", table_name="invitations")
    op.drop_index("ix_invitations_candidate_user_id", table_name="invitations")
    op.drop_index("ix_invitations_employer_id", table_name="invitations")
    op.drop_table("invitations")
