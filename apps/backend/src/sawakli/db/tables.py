"""SQLAlchemy Core table definitions for querying the real database.

Deliberately NOT registered on the same metadata Alembic uses
(`sawakli.db.session.Base.metadata`, wired up in alembic/env.py as
target_metadata) — this project's schema is built from hand-written raw-SQL
migrations (see alembic/versions/, ported from DATA-01), not from
SQLAlchemy models. If these tables were added to Base.metadata,
`alembic revision --autogenerate` would compare it against the live
database and see every other table as "unknown to metadata," which is
exactly the kind of surprise that leads to someone accidentally generating
a migration that drops half the schema. Keeping a separate MetaData here
means these are just typed handles for building SELECT/INSERT statements —
they're never a source of truth for what alembic upgrade actually builds.

As more layers add their own repositories, their tables belong here too,
following the same pattern — one shared, query-only metadata, decoupled
from Alembic's migration metadata.

Column shapes are copied exactly from Ahmed Ibrahim's DATA-01 deliverable
(002_backend_tables.sql, 005_connector_tables.sql) — kept in sync with
alembic/versions/0002_backend_tables.py and 0005_connector_tables.py.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, TIMESTAMP, UUID

metadata = sa.MetaData()

provider_enum = sa.Enum(
    "googleads",
    "metaads",
    "googleanalytics",
    "csv_demo",
    name="provider_enum",
    # the real type is created by alembic/versions/0001_...; never re-create it here
    create_type=False,
)

data_source_status_enum = sa.Enum(
    "connected",
    "disconnected",
    "syncing",
    "failed",
    "stale",
    "demo_data",
    name="data_source_status_enum",
    create_type=False,
)

sync_status_enum = sa.Enum(
    "pending",
    "running",
    "success",
    "failed",
    name="sync_status_enum",
    create_type=False,
)

# ------------------------------------------------------------------------------
# data_sources — Backend-owned (creates the row); Data Layer updates status
# fields only. Connector Layer has read-only access (INT-01 Ownership &
# Access Matrix) — used here only as a query target for check_connection_status(),
# never written to by this package.
# ------------------------------------------------------------------------------
data_sources_table = sa.Table(
    "data_sources",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
    sa.Column("provider", provider_enum, nullable=False),
    sa.Column("external_account_id", sa.Text, nullable=True),
    sa.Column("status", data_source_status_enum, nullable=False),
    sa.Column("last_synced_at", TIMESTAMP(timezone=False), nullable=True),
    sa.Column("sync_status", sync_status_enum, nullable=True),
    sa.Column("last_error", sa.Text, nullable=True),
    sa.Column("created_at", TIMESTAMP(timezone=False), nullable=False),
)

# ------------------------------------------------------------------------------
# connector_tokens — Connector Layer-owned EXCLUSIVELY (INT-01 §1.4). Keyed by
# data_source_id (UNIQUE), not org_id+provider — see Conflict #13.
# refresh_token_encrypted / expires_at / last_refreshed_at are all nullable:
# not every provider grant issues a refresh token or a fixed expiry.
# ------------------------------------------------------------------------------
connector_tokens_table = sa.Table(
    "connector_tokens",
    metadata,
    sa.Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    ),
    sa.Column("data_source_id", UUID(as_uuid=True), nullable=False, unique=True),
    sa.Column("provider", provider_enum, nullable=False),
    sa.Column("access_token_encrypted", BYTEA, nullable=False),
    sa.Column("refresh_token_encrypted", BYTEA, nullable=True),
    sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
    sa.Column("last_refreshed_at", TIMESTAMP(timezone=True), nullable=True),
)
