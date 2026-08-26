"""auth and jobs additions

Revision ID: 0010_auth_and_jobs_additions
Revises: 0009_seed_demo_data
Create Date: 2026-08-26 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_auth_and_jobs_additions"
down_revision: str | Sequence[str] | None = "0009_seed_demo_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("name", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "jobs",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_jobs_model_run_id", "jobs", ["model_run_id"])


def downgrade() -> None:
    op.drop_constraint("uq_jobs_model_run_id", "jobs", type_="unique")
    op.drop_column("jobs", "claimed_at")
    op.drop_column("users", "name")
