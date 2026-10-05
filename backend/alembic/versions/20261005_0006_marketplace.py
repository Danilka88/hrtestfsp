"""vacancies, applications, regular_tasks, task_submissions

Revision ID: 20261005_0006
Revises: 20261005_0005
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261005_0006"
down_revision: str | None = "20261005_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "employer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "specialization_id",
            sa.Integer(),
            sa.ForeignKey("specializations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("grade_code", sa.String(length=20), nullable=True),
        sa.Column("stack", sa.JSON(), nullable=False),
        sa.Column("salary_from", sa.Integer(), nullable=False),
        sa.Column("salary_to", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_vacancies_employer_id", "vacancies", ["employer_id"])
    op.create_index("ix_vacancies_status", "vacancies", ["status"])

    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "vacancy_id",
            sa.String(length=36),
            sa.ForeignKey("vacancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="sent"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_applications_vacancy_id", "applications", ["vacancy_id"])
    op.create_index("ix_applications_candidate_user_id", "applications", ["candidate_user_id"])
    op.create_index("ix_applications_status", "applications", ["status"])

    op.create_table(
        "regular_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "employer_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "specialization_id",
            sa.Integer(),
            sa.ForeignKey("specializations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("grade_code", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_regular_tasks_employer_id", "regular_tasks", ["employer_id"])

    op.create_table(
        "task_submissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("regular_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column("employer_feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_task_submissions_task_id", "task_submissions", ["task_id"])
    op.create_index("ix_task_submissions_candidate_user_id", "task_submissions", ["candidate_user_id"])


def downgrade() -> None:
    op.drop_index("ix_task_submissions_candidate_user_id", table_name="task_submissions")
    op.drop_index("ix_task_submissions_task_id", table_name="task_submissions")
    op.drop_table("task_submissions")
    op.drop_index("ix_regular_tasks_employer_id", table_name="regular_tasks")
    op.drop_table("regular_tasks")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_candidate_user_id", table_name="applications")
    op.drop_index("ix_applications_vacancy_id", table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_vacancies_status", table_name="vacancies")
    op.drop_index("ix_vacancies_employer_id", table_name="vacancies")
    op.drop_table("vacancies")
