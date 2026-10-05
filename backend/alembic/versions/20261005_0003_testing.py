"""specializations, grades, categories, items, survey_responses,
test_sessions, item_responses, grade_changes

Revision ID: 20261005_0003
Revises: 20261005_0002
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0003"
down_revision: Union[str, None] = "20261005_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "specializations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=64), nullable=False, server_default="it"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_specializations_code", "specializations", ["code"], unique=True)

    op.create_table(
        "grades",
        sa.Column("code", sa.String(length=20), primary_key=True),
        sa.Column("title", sa.String(length=60), nullable=False),
        sa.Column("rank_order", sa.Integer(), nullable=False),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("specialization_id", sa.Integer(),
                  sa.ForeignKey("specializations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grade_code", sa.String(length=20),
                  sa.ForeignKey("grades.code", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("specialization_id", "grade_code", name="uq_category"),
    )
    op.create_index("ix_categories_specialization_id", "categories", ["specialization_id"])
    op.create_index("ix_categories_grade_code", "categories", ["grade_code"])

    op.create_table(
        "items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("specialization_id", sa.Integer(),
                  sa.ForeignKey("specializations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("skill_tag", sa.String(length=64), nullable=False),
        sa.Column("item_type", sa.String(length=24), nullable=False, server_default="single_choice"),
        sa.Column("difficulty", sa.Float(), nullable=False),
        sa.Column("discrimination", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_exposure", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("exposure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_items_specialization_id", "items", ["specialization_id"])
    op.create_index("ix_items_skill_tag", "items", ["skill_tag"])
    op.create_index("ix_items_difficulty", "items", ["difficulty"])

    op.create_table(
        "survey_responses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("industry", sa.String(length=64), nullable=False),
        sa.Column("specialization_id", sa.Integer(),
                  sa.ForeignKey("specializations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_survey_responses_user_id", "survey_responses", ["user_id"])

    op.create_table(
        "test_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("specialization_id", sa.Integer(),
                  sa.ForeignKey("specializations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_grade", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("theta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("standard_error", sa.Float(), nullable=False, server_default="99"),
        sa.Column("result_grade", sa.String(length=20), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("category_id", sa.Integer(),
                  sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("grade_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_test_sessions_user_id", "test_sessions", ["user_id"])

    op.create_table(
        "item_responses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36),
                  sa.ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(length=36),
                  sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_item_responses_session_id", "item_responses", ["session_id"])

    op.create_table(
        "grade_changes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_grade", sa.String(length=20), nullable=True),
        sa.Column("to_grade", sa.String(length=20), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_grade_changes_user_id", "grade_changes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_grade_changes_user_id", table_name="grade_changes")
    op.drop_table("grade_changes")
    op.drop_index("ix_item_responses_session_id", table_name="item_responses")
    op.drop_table("item_responses")
    op.drop_index("ix_test_sessions_user_id", table_name="test_sessions")
    op.drop_table("test_sessions")
    op.drop_index("ix_survey_responses_user_id", table_name="survey_responses")
    op.drop_table("survey_responses")
    op.drop_index("ix_items_difficulty", table_name="items")
    op.drop_index("ix_items_skill_tag", table_name="items")
    op.drop_index("ix_items_specialization_id", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_categories_grade_code", table_name="categories")
    op.drop_index("ix_categories_specialization_id", table_name="categories")
    op.drop_table("categories")
    op.drop_table("grades")
    op.drop_index("ix_specializations_code", table_name="specializations")
    op.drop_table("specializations")
