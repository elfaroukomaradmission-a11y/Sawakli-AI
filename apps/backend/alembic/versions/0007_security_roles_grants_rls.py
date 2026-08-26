"""Security: roles, grants, and row-level security

Ported from Ahmed Ibrahim's DATA-01 deliverable (007_security_roles_grants_rls.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0007_security_roles_grants_rls
Revises: 0006_indexes_and_constraints
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0007_security_roles_grants_rls"
down_revision = "0006_indexes_and_constraints"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 007: Security — Roles, Grants & Row-Level Security
-- ============================================
-- Purpose: Enforce INT-01 Section 3 (Ownership & Access Matrix) at the
-- PostgreSQL level using roles, grants, and RLS policies.
--
-- Hard rule from INT-01 Section 3:
--   "No query against campaign, metric, or AI-output data executes without
--    an organization_id filter. A query missing this filter is a critical bug
--    regardless of which layer wrote it."
--
-- Build order: After 006 (tables and indexes must exist).
--
-- NOTE: Run this as a superuser or database owner.
-- ============================================

-- ==============================================================================
-- STEP 1: Create Layer Roles
-- ==============================================================================
-- These roles map 1:1 to the six layers in INT-01.
-- In production, each service connects with its own role credentials.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'backend_role') THEN
        CREATE ROLE backend_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'data_layer_role') THEN
        CREATE ROLE data_layer_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_layer_role') THEN
        CREATE ROLE ai_layer_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'connector_role') THEN
        CREATE ROLE connector_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'worker_role') THEN
        CREATE ROLE worker_role NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'readonly_role') THEN
        CREATE ROLE readonly_role NOLOGIN;
    END IF;
END
$$;

-- Grant schema usage to all roles
GRANT USAGE ON SCHEMA public TO backend_role, data_layer_role, ai_layer_role, connector_role, worker_role, readonly_role;

-- ==============================================================================
-- STEP 2: Backend Role Grants
-- ==============================================================================
-- Backend owns: users, organizations, organization_members, oauth_connections, jobs, execution_logs
-- Backend reads: all campaign/metric/AI tables (serves to UI)
-- Backend updates: recommendations.status ONLY (approval flow)

-- Full ownership of Backend tables
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO backend_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON organizations TO backend_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON organization_members TO backend_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON oauth_connections TO backend_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO backend_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON execution_logs TO backend_role;

-- Backend creates data_sources rows (connector setup)
GRANT SELECT, INSERT ON data_sources TO backend_role;

-- Backend reads all data for UI serving
GRANT SELECT ON campaigns TO backend_role;
GRANT SELECT ON ad_groups TO backend_role;
GRANT SELECT ON ads TO backend_role;
GRANT SELECT ON creatives TO backend_role;
GRANT SELECT ON daily_metrics TO backend_role;
GRANT SELECT ON ga_events TO backend_role;
GRANT SELECT ON feature_daily TO backend_role;
GRANT SELECT ON raw_api_responses TO backend_role;

-- Backend reads all AI output for UI serving
GRANT SELECT ON model_runs TO backend_role;
GRANT SELECT ON forecasts TO backend_role;
GRANT SELECT ON anomalies TO backend_role;
GRANT SELECT ON action_simulations TO backend_role;

-- Backend updates recommendations.status ONLY (approval/rejection flow)
GRANT SELECT ON recommendations TO backend_role;
GRANT UPDATE (status) ON recommendations TO backend_role;

-- ==============================================================================
-- STEP 3: Data Layer Role Grants
-- ==============================================================================
-- Data Layer owns: raw_api_responses, campaigns, ad_groups, ads, creatives,
--                  daily_metrics, ga_events, feature_daily
-- Data Layer updates: data_sources status columns only (sync scheduler)

-- Full ownership of Data Layer tables
GRANT SELECT, INSERT, UPDATE, DELETE ON raw_api_responses TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON campaigns TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ad_groups TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ads TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON creatives TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON daily_metrics TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ga_events TO data_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON feature_daily TO data_layer_role;

-- Data Layer updates data_sources status fields only (INT-01 1.1, 2.9)
GRANT SELECT ON data_sources TO data_layer_role;
GRANT UPDATE (status, sync_status, last_synced_at, last_error) ON data_sources TO data_layer_role;

-- Data Layer reads campaigns for feature engineering
GRANT SELECT ON campaigns TO data_layer_role;

-- ==============================================================================
-- STEP 4: AI Layer Role Grants
-- ==============================================================================
-- AI Layer owns: model_runs, forecasts, anomalies, recommendations (insert),
--                action_simulations
-- AI Layer reads: feature_daily, daily_metrics, campaigns

-- Full ownership of AI output tables
GRANT SELECT, INSERT, UPDATE, DELETE ON model_runs TO ai_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON forecasts TO ai_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON anomalies TO ai_layer_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON action_simulations TO ai_layer_role;

-- AI Layer inserts recommendations; Backend updates status
GRANT SELECT, INSERT ON recommendations TO ai_layer_role;

-- AI Layer reads feature source and raw metrics
GRANT SELECT ON feature_daily TO ai_layer_role;
GRANT SELECT ON daily_metrics TO ai_layer_role;
GRANT SELECT ON campaigns TO ai_layer_role;

-- ==============================================================================
-- STEP 5: Connector Role Grants
-- ==============================================================================
-- Connector Layer owns: connector_tokens EXCLUSIVELY.
-- No other layer reads, writes, or caches a token value.

GRANT SELECT, INSERT, UPDATE, DELETE ON connector_tokens TO connector_role;

-- Connector reads data_sources to verify sync targets and key by data_source_id
GRANT SELECT ON data_sources TO connector_role;

-- ==============================================================================
-- STEP 6: Worker Role Grants
-- ==============================================================================
-- Worker is the bridge between Backend and AI.
--   - Polls jobs table (reads status, writes model_run_id)
--   - Initializes model_runs row (INSERT id, org_id, user_id, started_at, status)
--   - Reads data_sources for sync targets

GRANT SELECT, UPDATE (model_run_id, status) ON jobs TO worker_role;
GRANT INSERT, SELECT ON model_runs TO worker_role;
GRANT SELECT ON data_sources TO worker_role;
GRANT SELECT ON organizations TO worker_role;
GRANT SELECT ON users TO worker_role;

-- ==============================================================================
-- STEP 7: Read-Only Role (Optional — for analytics, reporting, or UI backend)
-- ==============================================================================
GRANT SELECT ON users TO readonly_role;
GRANT SELECT ON organizations TO readonly_role;
GRANT SELECT ON organization_members TO readonly_role;
GRANT SELECT ON data_sources TO readonly_role;
GRANT SELECT ON oauth_connections TO readonly_role;
GRANT SELECT ON jobs TO readonly_role;
GRANT SELECT ON execution_logs TO readonly_role;
GRANT SELECT ON campaigns TO readonly_role;
GRANT SELECT ON ad_groups TO readonly_role;
GRANT SELECT ON ads TO readonly_role;
GRANT SELECT ON creatives TO readonly_role;
GRANT SELECT ON daily_metrics TO readonly_role;
GRANT SELECT ON ga_events TO readonly_role;
GRANT SELECT ON feature_daily TO readonly_role;
GRANT SELECT ON raw_api_responses TO readonly_role;
GRANT SELECT ON model_runs TO readonly_role;
GRANT SELECT ON forecasts TO readonly_role;
GRANT SELECT ON anomalies TO readonly_role;
GRANT SELECT ON recommendations TO readonly_role;
GRANT SELECT ON action_simulations TO readonly_role;
-- connector_tokens EXCLUDED — even readonly cannot see tokens

-- ==============================================================================
-- STEP 8: Row-Level Security (RLS) — Organization Isolation
-- ==============================================================================
-- INT-01 hard rule: every query against campaign/metric/AI data must filter
-- by organization_id. RLS enforces this at the database level.
--
-- Usage in application:
--   SET app.current_org_id = 'uuid-here';
--   SELECT * FROM campaigns;  -- only sees rows for that org
--
-- If app.current_org_id is not set, RLS defaults to seeing nothing
-- (FAIL-CLOSED security model).

-- Helper function: safe org_id extraction
CREATE OR REPLACE FUNCTION get_current_org_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_org_id', true), '')::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- ------------------------------------------------------------------------------
-- Enable RLS on all org-scoped tables
-- ------------------------------------------------------------------------------
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE ga_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE action_simulations ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_api_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_connections ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- Create org-isolation policies (FAIL CLOSED: if org_id not set, returns nothing)
-- ------------------------------------------------------------------------------
CREATE POLICY org_isolation_campaigns ON campaigns
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_daily_metrics ON daily_metrics
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_ga_events ON ga_events
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_feature_daily ON feature_daily
    USING (entity_id IN (SELECT id FROM campaigns WHERE organization_id = get_current_org_id()));

CREATE POLICY org_isolation_jobs ON jobs
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_execution_logs ON execution_logs
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_model_runs ON model_runs
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_forecasts ON forecasts
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_anomalies ON anomalies
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_recommendations ON recommendations
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_action_simulations ON action_simulations
    USING (recommendation_id IN (
        SELECT id FROM recommendations WHERE organization_id = get_current_org_id()
    ));

CREATE POLICY org_isolation_raw_api ON raw_api_responses
    USING (data_source_id IN (
        SELECT id FROM data_sources WHERE organization_id = get_current_org_id()
    ));

CREATE POLICY org_isolation_data_sources ON data_sources
    USING (organization_id = get_current_org_id());

CREATE POLICY org_isolation_oauth ON oauth_connections
    USING (organization_id = get_current_org_id());

-- ------------------------------------------------------------------------------
-- Bypass RLS for table owners (migration runner) but enforce for app roles
-- ------------------------------------------------------------------------------
-- Table owner (who ran migrations) bypasses RLS by default.
-- App roles must explicitly set app.current_org_id or see nothing.

-- ==============================================================================
-- Schema Version
-- ==============================================================================
INSERT INTO schema_migrations (version, description)
VALUES ('007', 'Security: roles, grants, and row-level security')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP POLICY IF EXISTS org_isolation_campaigns ON campaigns;
DROP POLICY IF EXISTS org_isolation_daily_metrics ON daily_metrics;
DROP POLICY IF EXISTS org_isolation_ga_events ON ga_events;
DROP POLICY IF EXISTS org_isolation_feature_daily ON feature_daily;
DROP POLICY IF EXISTS org_isolation_jobs ON jobs;
DROP POLICY IF EXISTS org_isolation_execution_logs ON execution_logs;
DROP POLICY IF EXISTS org_isolation_model_runs ON model_runs;
DROP POLICY IF EXISTS org_isolation_forecasts ON forecasts;
DROP POLICY IF EXISTS org_isolation_anomalies ON anomalies;
DROP POLICY IF EXISTS org_isolation_recommendations ON recommendations;
DROP POLICY IF EXISTS org_isolation_action_simulations ON action_simulations;
DROP POLICY IF EXISTS org_isolation_raw_api ON raw_api_responses;
DROP POLICY IF EXISTS org_isolation_data_sources ON data_sources;
DROP POLICY IF EXISTS org_isolation_oauth ON oauth_connections;

ALTER TABLE campaigns DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics DISABLE ROW LEVEL SECURITY;
ALTER TABLE ga_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE feature_daily DISABLE ROW LEVEL SECURITY;
ALTER TABLE jobs DISABLE ROW LEVEL SECURITY;
ALTER TABLE execution_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE model_runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE forecasts DISABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies DISABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations DISABLE ROW LEVEL SECURITY;
ALTER TABLE action_simulations DISABLE ROW LEVEL SECURITY;
ALTER TABLE raw_api_responses DISABLE ROW LEVEL SECURITY;
ALTER TABLE data_sources DISABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_connections DISABLE ROW LEVEL SECURITY;

DROP FUNCTION IF EXISTS get_current_org_id();

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'backend_role') THEN
        DROP OWNED BY backend_role;
        DROP ROLE backend_role;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'data_layer_role') THEN
        DROP OWNED BY data_layer_role;
        DROP ROLE data_layer_role;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_layer_role') THEN
        DROP OWNED BY ai_layer_role;
        DROP ROLE ai_layer_role;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'connector_role') THEN
        DROP OWNED BY connector_role;
        DROP ROLE connector_role;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'worker_role') THEN
        DROP OWNED BY worker_role;
        DROP ROLE worker_role;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'readonly_role') THEN
        DROP OWNED BY readonly_role;
        DROP ROLE readonly_role;
    END IF;
END
$$;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
