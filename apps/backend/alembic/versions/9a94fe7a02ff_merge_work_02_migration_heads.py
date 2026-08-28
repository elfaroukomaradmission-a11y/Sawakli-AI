"""merge WORK-02 migration heads

Revision ID: 9a94fe7a02ff
Revises: 0011_jobs_one_inflight_per_org, 0011_jobs_retry_timeout_error
Create Date: 2026-08-28 15:13:15.058674
"""

from collections.abc import Sequence

revision: str = "9a94fe7a02ff"
down_revision: str | Sequence[str] | None = (
    "0011_jobs_one_inflight_per_org",
    "0011_jobs_retry_timeout_error",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
