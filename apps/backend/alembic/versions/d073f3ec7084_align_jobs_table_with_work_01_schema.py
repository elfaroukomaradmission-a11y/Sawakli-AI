"""align jobs table with work 01 schema

Revision ID: d073f3ec7084

Revises:

Create Date: 2026-08-25 02:05:12.772567
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "d073f3ec7084"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "campaign_ids",
            JSONB(),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "triggered_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "priority",
            sa.String(),
            nullable=False,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "model_run_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.drop_column("jobs", "payload")
    op.drop_column("jobs", "updated_at")

    op.create_unique_constraint(
        "uq_jobs_model_run_id",
        "jobs",
        ["model_run_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_jobs_model_run_id",
        "jobs",
        type_="unique",
    )

    op.add_column(
        "jobs",
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.drop_column("jobs", "model_run_id")
    op.drop_column("jobs", "priority")
    op.drop_column("jobs", "triggered_by_user_id")
    op.drop_column("jobs", "campaign_ids")
    op.drop_column("jobs", "organization_id")

