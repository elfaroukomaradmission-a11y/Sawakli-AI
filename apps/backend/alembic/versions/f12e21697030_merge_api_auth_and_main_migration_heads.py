"""merge api auth and main migration heads

Revision ID: f12e21697030
Revises: 0009_seed_demo_data, 07d519400bd0
Create Date: 2026-08-26 03:56:34.307521
"""

from collections.abc import Sequence

revision: str = "f12e21697030"
down_revision: str | Sequence[str] | None = ("0009_seed_demo_data", "07d519400bd0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
