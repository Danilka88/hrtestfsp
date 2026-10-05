"""employer_profiles, employer_needs, selections, selection_candidates

Revision ID: 20261005_0004
Revises: 20261005_0003
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0004"
down_revision: Union[str, None] = "20261005_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employer_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_employer_profiles_user_id", "employer_profiles", ["user_id"], unique=True)

    op.create_table(
        "employer_needs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employer_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("specialization_id", sa.Integer(),
                  sa.ForeignKey("specializations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("grade_code", sa.String(length=20), nullable=True),
        sa.Column("stack", sa.JSON(), nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_employer_needs_employer_id", "employer_needs", ["employer_id"])

    op.create_table(
        "selections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("employer_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("need_id", sa.String(length=36),
                  sa.ForeignKey("employer_needs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_selection_id", sa.String(length=36),
                  sa.ForeignKey("selections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("rubric_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_selections_employer_id", "selections", ["employer_id"])

    op.create_table(
        "selection_candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("selection_id", sa.String(length=36),
                  sa.ForeignKey("selections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_user_id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("missing", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("selection_id", "candidate_user_id", name="uq_selection_candidate"),
    )
    op.create_index("ix_selection_candidates_selection_id", "selection_candidates", ["selection_id"])
    op.create_index("ix_selection_candidates_candidate_user_id", "selection_candidates",
                    ["candidate_user_id"])


def downgrade() -> None:
    op.drop_index("ix_selection_candidates_candidate_user_id", table_name="selection_candidates")
    op.drop_index("ix_selection_candidates_selection_id", table_name="selection_candidates")
    op.drop_table("selection_candidates")
    op.drop_index("ix_selections_employer_id", table_name="selections")
    op.drop_table("selections")
    op.drop_index("ix_employer_needs_employer_id", table_name="employer_needs")
    op.drop_table("employer_needs")
    op.drop_index("ix_employer_profiles_user_id", table_name="employer_profiles")
    op.drop_table("employer_profiles")
