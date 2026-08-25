"""Extensions & enumerated types

Ported from Ahmed Ibrahim's DATA-01 deliverable (001_extensions_and_enums.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0001_extensions_and_enums
Revises: None
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0001_extensions_and_enums"
down_revision = None
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 001: Extensions & Enumerated Types
-- ============================================
-- Purpose: Enable required PostgreSQL extensions and create all ENUM types
-- defined in INT-01 Section 1 (Canonical Data Model).
--
-- Build order: FIRST — no dependencies.
-- ============================================

-- ------------------------------------------------------------------------------
-- Extensions
-- ------------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- For UUID generation fallback
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- For gen_random_uuid() (preferred)

-- ------------------------------------------------------------------------------
-- Provider & Platform Enums (used across multiple layers)
-- ------------------------------------------------------------------------------
CREATE TYPE provider_enum AS ENUM (
    'googleads',
    'metaads',
    'googleanalytics',
    'csv_demo'
);

CREATE TYPE platform_enum AS ENUM (
    'meta',
    'google'
);

-- ------------------------------------------------------------------------------
-- Data Source Lifecycle Enums
-- ------------------------------------------------------------------------------
CREATE TYPE data_source_status_enum AS ENUM (
    'connected',
    'disconnected',
    'syncing',
    'failed',
    'stale',
    'demo_data'
);

CREATE TYPE sync_status_enum AS ENUM (
    'pending',
    'running',
    'success',
    'failed'
);

-- ------------------------------------------------------------------------------
-- OAuth Connection Status
-- ------------------------------------------------------------------------------
CREATE TYPE oauth_status_enum AS ENUM (
    'connected',
    'expired',
    'revoked'
);

-- ------------------------------------------------------------------------------
-- Job Lifecycle Enum (Backend → Worker handoff)
-- ------------------------------------------------------------------------------
CREATE TYPE job_status_enum AS ENUM (
    'PENDING',
    'RUNNING',
    'SUCCESS',
    'FAILED',
    'CANCELLED',
    'PARTIAL_SUCCESS'
);

CREATE TYPE job_priority_enum AS ENUM (
    'HIGH',
    'LOW'
);

-- ------------------------------------------------------------------------------
-- Campaign / Ad Structure Status (generic, values not locked in INT-01)
-- ------------------------------------------------------------------------------
CREATE TYPE campaign_status_enum AS ENUM (
    'active',
    'paused',
    'removed',
    'unknown'
);

-- ------------------------------------------------------------------------------
-- AI Output Enums
-- ------------------------------------------------------------------------------
CREATE TYPE model_run_status_enum AS ENUM (
    'RUNNING',
    'SUCCESS',
    'FAILED',
    'CANCELLED',
    'PARTIAL_SUCCESS'
);

CREATE TYPE anomaly_severity_enum AS ENUM (
    'low',
    'medium',
    'high'
);

CREATE TYPE anomaly_direction_enum AS ENUM (
    'above',
    'below'
);

CREATE TYPE recommendation_status_enum AS ENUM (
    'pending',
    'approved',
    'rejected',
    'marked_done',
    'needs_review'
);

CREATE TYPE risk_rating_enum AS ENUM (
    'low',
    'medium',
    'high'
);

CREATE TYPE simulation_scenario_enum AS ENUM (
    'budget_decrease_20',
    'budget_increase_15',
    'pause'
);

-- ------------------------------------------------------------------------------
-- Schema Version Tracking (used by Migration 008)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

INSERT INTO schema_migrations (version, description)
VALUES ('001', 'Extensions and enumerated types')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS schema_migrations;
DROP TYPE IF EXISTS simulation_scenario_enum;
DROP TYPE IF EXISTS risk_rating_enum;
DROP TYPE IF EXISTS recommendation_status_enum;
DROP TYPE IF EXISTS anomaly_direction_enum;
DROP TYPE IF EXISTS anomaly_severity_enum;
DROP TYPE IF EXISTS model_run_status_enum;
DROP TYPE IF EXISTS campaign_status_enum;
DROP TYPE IF EXISTS job_priority_enum;
DROP TYPE IF EXISTS job_status_enum;
DROP TYPE IF EXISTS oauth_status_enum;
DROP TYPE IF EXISTS sync_status_enum;
DROP TYPE IF EXISTS data_source_status_enum;
DROP TYPE IF EXISTS platform_enum;
DROP TYPE IF EXISTS provider_enum;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
