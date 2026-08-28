"""jobs: one in-flight job per organization

Revision ID: 0011_jobs_one_inflight_per_org
Revises: 0010_auth_and_jobs_additions
Create Date: 2026-08-26 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_jobs_one_inflight_per_org"
down_revision: str | Sequence[str] | None = "0010_auth_and_jobs_additions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Guarantees at most one PENDING or RUNNING job per organization, even under
# concurrent requests. API-04's refresh endpoint checks for an in-flight job
# before inserting, but that check-then-insert has a race window on its own;
# this constraint is the actual backstop — a second concurrent insert fails
# with IntegrityError, which the endpoint catches and turns into "here's the
# job that won" instead of a duplicate row.
_INDEX_NAME = "uq_jobs_org_inflight"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "jobs",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="jobs")
