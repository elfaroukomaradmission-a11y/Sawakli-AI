"""Verification helpers and schema_version tracking

Ported from Ahmed Ibrahim's DATA-01 deliverable (008_verify_and_helpers.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0008_verify_and_helpers
Revises: 0007_security_roles_grants_rls
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0008_verify_and_helpers"
down_revision = "0007_security_roles_grants_rls"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 008: Verification Helpers & Fresh-Build Validation
-- ============================================
-- Purpose: Provide views and functions to verify that the schema matches
-- INT-01 exactly — tables, columns, constraints, indexes, and roles.
--
-- Build order: LAST (depends on everything).
-- ============================================

-- ==============================================================================
-- 1. Schema Inventory View
-- ==============================================================================
-- Lists every table, its owner layer, column count, and key constraints.
-- Compare this against INT-01 Section 1.

CREATE OR REPLACE VIEW v_schema_inventory AS
SELECT
    t.table_name,
    CASE
        WHEN t.table_name IN ('users', 'organizations', 'organization_members', 'oauth_connections', 'jobs', 'execution_logs')
            THEN 'Backend'
        WHEN t.table_name IN ('raw_api_responses', 'campaigns', 'ad_groups', 'ads', 'creatives', 'daily_metrics', 'ga_events', 'feature_daily')
            THEN 'Data Layer'
        WHEN t.table_name IN ('model_runs', 'forecasts', 'anomalies', 'recommendations', 'action_simulations')
            THEN 'AI Layer'
        WHEN t.table_name = 'connector_tokens'
            THEN 'Connector Layer'
        WHEN t.table_name IN ('schema_migrations', 'schema_version')
            THEN 'Meta'
        ELSE 'Unknown'
    END AS owner_layer,
    COUNT(c.column_name) AS column_count,
    COALESCE(
        (SELECT string_agg(DISTINCT tc.constraint_type, ', ' ORDER BY tc.constraint_type)
         FROM information_schema.table_constraints tc
         WHERE tc.table_name = t.table_name
           AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY', 'CHECK')),
        'NONE'
    ) AS constraints_present
FROM information_schema.tables t
LEFT JOIN information_schema.columns c ON c.table_name = t.table_name AND c.table_schema = 'public'
WHERE t.table_schema = 'public'
  AND t.table_type = 'BASE TABLE'
GROUP BY t.table_name
ORDER BY owner_layer, t.table_name;

COMMENT ON VIEW v_schema_inventory IS 'Canonical inventory of all tables per INT-01 Section 1. Use to verify fresh builds.';

-- ==============================================================================
-- 2. Index Verification View
-- ==============================================================================
-- Lists every index with its table and purpose for quick audit.

CREATE OR REPLACE VIEW v_index_inventory AS
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

COMMENT ON VIEW v_index_inventory IS 'Complete index list for performance audit against INT-01 Section 6.';

-- ==============================================================================
-- 3. Role Permission Verification View
-- ==============================================================================
-- Lists every role and what it can do on each table.

CREATE OR REPLACE VIEW v_role_permissions AS
SELECT
    grantee,
    table_name,
    privilege_type
FROM information_schema.table_privileges
WHERE grantee IN ('backend_role', 'data_layer_role', 'ai_layer_role', 'connector_role', 'worker_role', 'readonly_role')
  AND table_schema = 'public'
ORDER BY grantee, table_name, privilege_type;

COMMENT ON VIEW v_role_permissions IS 'Permission matrix for verifying INT-01 Section 3 Ownership & Access Matrix.';

-- ==============================================================================
-- 4. Fresh-Build Verification Function
-- ==============================================================================
-- Run this after all migrations to confirm the database matches INT-01.
-- Returns a report of any discrepancies.

CREATE OR REPLACE FUNCTION verify_int01_schema()
RETURNS TABLE (
    check_name TEXT,
    expected INT,
    actual INT,
    status TEXT
) AS $$
DECLARE
    v_count INT;
BEGIN
    -- Check 1: Table count (23 tables = 19 domain + 2 meta + 2 helper views)
    -- Actually: 19 domain tables + schema_migrations + schema_version = 21
    -- Wait, let me recount: 7 backend + 8 data + 5 ai + 1 connector + 2 meta = 23
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    RETURN QUERY SELECT 'Total tables (incl. meta)'::TEXT, 23, v_count,
        CASE WHEN v_count = 23 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 2: ENUM types count (14 per Migration 001)
    SELECT COUNT(*) INTO v_count
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public' AND t.typtype = 'e';
    RETURN QUERY SELECT 'ENUM types'::TEXT, 14, v_count,
        CASE WHEN v_count = 14 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 3: Backend tables exist (7 tables)
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
      AND table_name IN ('users', 'organizations', 'organization_members', 'data_sources', 'oauth_connections', 'jobs', 'execution_logs');
    RETURN QUERY SELECT 'Backend tables'::TEXT, 7, v_count,
        CASE WHEN v_count = 7 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 4: Data Layer tables exist (8 tables)
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
      AND table_name IN ('raw_api_responses', 'campaigns', 'ad_groups', 'ads', 'creatives', 'daily_metrics', 'ga_events', 'feature_daily');
    RETURN QUERY SELECT 'Data Layer tables'::TEXT, 8, v_count,
        CASE WHEN v_count = 8 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 5: AI Layer tables exist (5 tables)
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
      AND table_name IN ('model_runs', 'forecasts', 'anomalies', 'recommendations', 'action_simulations');
    RETURN QUERY SELECT 'AI Layer tables'::TEXT, 5, v_count,
        CASE WHEN v_count = 5 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 6: Connector table exists (1 table, provisional)
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
      AND table_name = 'connector_tokens';
    RETURN QUERY SELECT 'Connector table (provisional)'::TEXT, 1, v_count,
        CASE WHEN v_count = 1 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 7: RLS enabled on org-scoped tables (14 tables)
    -- campaigns, daily_metrics, ga_events, feature_daily, jobs, execution_logs,
    -- model_runs, forecasts, anomalies, recommendations, action_simulations,
    -- raw_api_responses, data_sources, oauth_connections
    SELECT COUNT(*) INTO v_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relrowsecurity = true;
    RETURN QUERY SELECT 'RLS-enabled tables'::TEXT, 14, v_count,
        CASE WHEN v_count = 14 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 8: Layer roles exist (6 roles)
    SELECT COUNT(*) INTO v_count
    FROM pg_roles
    WHERE rolname IN ('backend_role', 'data_layer_role', 'ai_layer_role', 'connector_role', 'worker_role', 'readonly_role');
    RETURN QUERY SELECT 'Layer roles'::TEXT, 6, v_count,
        CASE WHEN v_count = 6 THEN 'PASS' ELSE 'FAIL' END;

    -- Check 9: Organization_id present on directly-scoped tables (11 tables)
    -- Excludes action_simulations (scoped via recommendation_id FK)
    -- Excludes raw_api_responses (scoped via data_source_id FK)
    SELECT COUNT(*) INTO v_count
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name IN ('campaigns', 'daily_metrics', 'ga_events', 'jobs', 'execution_logs',
                          'model_runs', 'forecasts', 'anomalies', 'recommendations',
                          'data_sources', 'oauth_connections')
      AND column_name = 'organization_id';
    RETURN QUERY SELECT 'Org_id columns on scoped tables'::TEXT, 11, v_count,
        CASE WHEN v_count = 11 THEN 'PASS' ELSE 'FAIL' END;

    RETURN;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION verify_int01_schema() IS 'Run after fresh build to validate schema against INT-01. All checks should return PASS.';

-- ==============================================================================
-- 5. Schema Version Tracking Table (already created in 001, ensure latest)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS schema_version (
    id          SERIAL PRIMARY KEY,
    version     TEXT NOT NULL UNIQUE,
    applied_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

-- Seed with all migration versions for a complete audit trail
INSERT INTO schema_version (version, description) VALUES
('001', 'Extensions and enumerated types'),
('002', 'Backend / Auth-owned tables'),
('003', 'Data Layer-owned tables'),
('004', 'AI Layer-owned tables'),
('005', 'Connector Layer-owned table (PROVISIONAL)'),
('006', 'Performance indexes and partial unique constraints'),
('007', 'Security: roles, grants, and row-level security'),
('008', 'Verification helpers and schema validation')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS schema_version;
DROP FUNCTION IF EXISTS verify_int01_schema();
DROP VIEW IF EXISTS v_role_permissions;
DROP VIEW IF EXISTS v_index_inventory;
DROP VIEW IF EXISTS v_schema_inventory;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
