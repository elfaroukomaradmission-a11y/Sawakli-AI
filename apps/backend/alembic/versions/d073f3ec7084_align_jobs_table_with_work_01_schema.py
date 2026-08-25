"""align jobs table with work 01 schema

Revision ID: d073f3ec7084
Revises:
Create Date: 2026-08-25 02:05:12.772567
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "d073f3ec7084"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "campaign_ids",
            JSONB,
            nullable=True,
        ),
        sa.Column(
            "triggered_by_user_id",
            UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(32),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(32),
            server_default=sa.text("'NORMAL'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "model_run_id",
            UUID(as_uuid=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_run_id", name="uq_jobs_model_run_id"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
