"""Connector Layer-owned table (connector_tokens)

Ported from Ahmed Ibrahim's DATA-01 deliverable (005_connector_tables.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0005_connector_tables
Revises: 0004_ai_layer_tables
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0005_connector_tables"
down_revision = "0004_ai_layer_tables"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 005: Connector Layer-Owned Table
-- ============================================
-- Purpose: Create the connector_tokens table per INT-01 Section 1.4.
--
-- STATUS: PROVISIONAL — pending confirmation from Youssef, Abdelrahman, and Elfarouk.
--
-- Owner: Connector Layer EXCLUSIVELY.
-- Hard rule: No other layer ever reads, writes, or caches a token value.
-- Keyed by data_source_id (not org_id+provider) since an org can have multiple
-- accounts on the same provider.
--
-- Build order: After 002 (depends on data_sources).
-- ============================================

CREATE TABLE connector_tokens (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id          UUID NOT NULL,
    provider                provider_enum NOT NULL,
    access_token_encrypted  BYTEA NOT NULL,
    refresh_token_encrypted BYTEA,
    expires_at              TIMESTAMPTZ,
    last_refreshed_at       TIMESTAMPTZ,

    CONSTRAINT fk_connector_tokens_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE,

    -- One token set per data_source (one row per connected account)
    CONSTRAINT uq_connector_tokens_data_source UNIQUE (data_source_id)
);

COMMENT ON TABLE connector_tokens IS 'PROVISIONAL. Connector Layer-owned EXCLUSIVELY. No other layer touches this table.';
COMMENT ON COLUMN connector_tokens.access_token_encrypted IS 'Encrypted at rest. Never leaves Connector Layer.';
COMMENT ON COLUMN connector_tokens.refresh_token_encrypted IS 'Encrypted at rest. Nullable if provider does not use refresh tokens.';

-- ------------------------------------------------------------------------------
-- Schema Version
-- ------------------------------------------------------------------------------
INSERT INTO schema_migrations (version, description)
VALUES ('005', 'Connector Layer-owned table (PROVISIONAL)')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS connector_tokens;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
