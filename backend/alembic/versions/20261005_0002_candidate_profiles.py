"""candidate_profiles

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261005_0002"
down_revision: str | None = "20261005_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("contacts", sa.JSON(), nullable=False),
        sa.Column("specialization", sa.String(length=120), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=True),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("stack", sa.JSON(), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False),
        sa.Column("soft_skills", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("resume_source", sa.String(length=16), nullable=False, server_default="form"),
        sa.Column("resume_filename", sa.String(length=255), nullable=True),
        sa.Column("raw_resume_text", sa.Text(), nullable=True),
        sa.Column("privacy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_candidate_profiles_user_id", "candidate_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_candidate_profiles_user_id", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")
