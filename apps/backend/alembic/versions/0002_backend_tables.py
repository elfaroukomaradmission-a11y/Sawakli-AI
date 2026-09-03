"""Backend / Auth-owned tables

Ported from Ahmed Ibrahim's DATA-01 deliverable (002_backend_tables.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0002_backend_tables
Revises: 0001_extensions_and_enums
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0002_backend_tables"
down_revision = "0001_extensions_and_enums"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 002: Backend / Auth-Owned Tables
-- ============================================
-- Purpose: Create the seven tables owned exclusively by the Backend layer
-- per INT-01 Section 1.1.
--
-- Owner: Backend (sole logical writer).
-- Read access: Other layers receive resolved data, never query these directly.
-- Build order: After 001 (depends on ENUMs).
-- ============================================

-- ------------------------------------------------------------------------------
-- 1. organizations
-- Tenant boundary. Created atomically with the first user in the same transaction.
-- ------------------------------------------------------------------------------
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR NOT NULL,
    plan        VARCHAR,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE organizations IS 'Tenant boundary. Backend-owned. Created atomically with first user.';

-- ------------------------------------------------------------------------------
-- 2. users
-- Login identity. hashed_password NEVER leaves the Backend in any response.
-- ------------------------------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL,  -- bcrypt >= 12 rounds
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_users_email UNIQUE (email)
);

COMMENT ON TABLE users IS 'Login identity. Backend-owned. hashed_password never leaves Backend.';
COMMENT ON COLUMN users.hashed_password IS 'bcrypt hash with cost >= 12. Never returned in any API response.';

-- ------------------------------------------------------------------------------
-- 3. organization_members
-- Workspace membership. Data Layer and AI Layer never read this table —
-- they only need organization_id, not who belongs to it.
-- ------------------------------------------------------------------------------
CREATE TABLE organization_members (
    user_id         UUID NOT NULL,
    organization_id UUID NOT NULL,
    role            VARCHAR NOT NULL,

    PRIMARY KEY (user_id, organization_id),

    CONSTRAINT fk_org_members_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_org_members_org
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

COMMENT ON TABLE organization_members IS 'Workspace membership. Backend-owned. Data/AI layers never read this.';

-- ------------------------------------------------------------------------------
-- 4. data_sources
-- Canonical replacement for the old separate "accounts" concept.
-- One row per connected external account or demo/CSV source.
--
-- Ownership split:
--   - Backend: creates the row on connector setup.
--   - Data Layer: updates status columns only (sync scheduler).
-- ------------------------------------------------------------------------------
CREATE TABLE data_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    provider            provider_enum NOT NULL,
    external_account_id TEXT,                              -- nullable for csv_demo
    status              data_source_status_enum NOT NULL DEFAULT 'disconnected',
    last_synced_at      TIMESTAMP,
    sync_status         sync_status_enum,
    last_error          TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_data_sources_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
);

COMMENT ON TABLE data_sources IS 'Canonical replacement for accounts. Backend creates; Data Layer updates status fields only.';
COMMENT ON COLUMN data_sources.external_account_id IS 'Nullable for CSV/demo sources per INT-01.';

-- ------------------------------------------------------------------------------
-- 5. oauth_connections
-- STATUS/LINK RECORD ONLY — never contains a token value.
-- The actual token lives in connector_tokens (Migration 005).
-- ------------------------------------------------------------------------------
CREATE TABLE oauth_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    data_source_id  UUID NOT NULL,
    platform        provider_enum NOT NULL,
    status          oauth_status_enum NOT NULL DEFAULT 'connected',
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_oauth_connections_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_oauth_connections_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
);

COMMENT ON TABLE oauth_connections IS 'Status/link record ONLY. Never stores token values. Backend-owned.';

-- ------------------------------------------------------------------------------
-- 6. jobs
-- Backend's own trigger/poll ticket — distinct from model_runs.
-- model_run_id lets Backend correlate a ticket to its AI output once the
-- Worker knows it (INT-01 Section 2.5).
-- ------------------------------------------------------------------------------
CREATE TABLE jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    campaign_ids        JSONB,                              -- array of campaign UUIDs
    triggered_by_user_id UUID,
    status              job_status_enum NOT NULL DEFAULT 'PENDING',
    priority            job_priority_enum NOT NULL DEFAULT 'LOW',
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_run_id        UUID,                               -- nullable until Worker knows it

    CONSTRAINT fk_jobs_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_jobs_triggered_by
        FOREIGN KEY (triggered_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON TABLE jobs IS 'Backend trigger/poll ticket. model_run_id links to AI output. Backend-owned.';
COMMENT ON COLUMN jobs.campaign_ids IS 'JSONB array of campaign UUIDs. Optional — NULL means all org campaigns.';

-- ------------------------------------------------------------------------------
-- 7. execution_logs
-- Append-only audit trail. approval_reference guards against duplicate execution.
-- ------------------------------------------------------------------------------
CREATE TABLE execution_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    user_id             UUID,
    recommendation_id   UUID,
    action              VARCHAR NOT NULL,
    approval_reference  UUID NOT NULL,
    timestamp           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_exec_logs_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_exec_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON TABLE execution_logs IS 'Append-only audit trail. approval_reference prevents duplicate execution. Backend-owned.';

-- ------------------------------------------------------------------------------
-- Schema Version
-- ------------------------------------------------------------------------------
INSERT INTO schema_migrations (version, description)
VALUES ('002', 'Backend / Auth-owned tables')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS execution_logs;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS oauth_connections;
DROP TABLE IF EXISTS data_sources;
DROP TABLE IF EXISTS organization_members;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS organizations;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
