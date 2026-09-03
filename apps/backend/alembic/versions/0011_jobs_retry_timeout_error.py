"""jobs retry timeout error

Revision ID: 0011_jobs_retry_timeout_error
Revises: 0010_auth_and_jobs_additions
Create Date: 2026-08-28 08:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_jobs_retry_timeout_error"
down_revision: str | None = "0010_auth_and_jobs_additions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add ERROR to job_status_enum
    op.execute("ALTER TYPE job_status_enum ADD VALUE IF NOT EXISTS 'ERROR'")

    # 2. Add columns to jobs table
    op.add_column(
        "jobs",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "jobs",
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="300"),
    )

    # 3. Add partial unique constraint: at most one in-flight job per organization
    op.create_index(
        "uq_jobs_one_inflight_per_org",
        "jobs",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_jobs_one_inflight_per_org", table_name="jobs", if_exists=True)
    op.drop_column("jobs", "timeout_seconds")
    op.drop_column("jobs", "next_retry_at")
    op.drop_column("jobs", "max_retries")
    op.drop_column("jobs", "retry_count")
