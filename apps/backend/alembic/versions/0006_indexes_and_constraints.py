"""Performance indexes and partial unique constraints

Ported from Ahmed Ibrahim's DATA-01 deliverable (006_indexes_and_constraints.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0006_indexes_and_constraints
Revises: 0005_connector_tables
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0006_indexes_and_constraints"
down_revision = "0005_connector_tables"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 006: Performance Indexes & Partial Unique Constraints
-- ============================================
-- Purpose: Add all indexes required by INT-01 contracts and performance needs.
--
-- Design principles from INT-01:
--   1. Every query touching campaign/metric/AI data carries WHERE organization_id = :org_id
--   2. Time-series queries dominate (daily_metrics, ga_events, feature_daily, forecasts)
--   3. Worker polls jobs by status + priority + created_at
--   4. Idempotent inserts require unique composite indexes
--
-- Build order: After 005 (all tables must exist).
-- ============================================

-- ==============================================================================
-- BACKEND TABLES
-- ==============================================================================

-- users: login lookups by email
CREATE INDEX idx_users_email ON users(email);

-- organization_members: fast membership checks
CREATE INDEX idx_org_members_org ON organization_members(organization_id);
CREATE INDEX idx_org_members_user ON organization_members(user_id);

-- data_sources: connector-status endpoint (INT-01 2.1)
CREATE INDEX idx_data_sources_org_status
    ON data_sources(organization_id, status, last_synced_at);

-- data_sources: sync scheduler lookups
CREATE INDEX idx_data_sources_provider_status
    ON data_sources(provider, status) WHERE status IN ('connected', 'stale');

-- oauth_connections: status screen lookups
CREATE INDEX idx_oauth_connections_org
    ON oauth_connections(organization_id, status);

-- jobs: Worker queue polling (status + priority + created_at)
CREATE INDEX idx_jobs_queue_poll
    ON jobs(status, priority, created_at)
    WHERE status IN ('PENDING', 'RUNNING');

-- jobs: correlate to AI output
CREATE INDEX idx_jobs_model_run ON jobs(model_run_id) WHERE model_run_id IS NOT NULL;

-- jobs: org-scoped listing
CREATE INDEX idx_jobs_org ON jobs(organization_id, created_at DESC);

-- execution_logs: audit trail by org + time
CREATE INDEX idx_exec_logs_org_time ON execution_logs(organization_id, timestamp DESC);
CREATE INDEX idx_exec_logs_recommendation ON execution_logs(recommendation_id);

-- ==============================================================================
-- DATA LAYER TABLES
-- ==============================================================================

-- raw_api_responses: idempotent insert key (INT-01 1.2)
CREATE UNIQUE INDEX idx_raw_api_idempotent
    ON raw_api_responses(data_source_id, endpoint, fetched_at);

-- raw_api_responses: ingestion pipeline lookups
CREATE INDEX idx_raw_api_data_source_fetched
    ON raw_api_responses(data_source_id, fetched_at DESC);

-- campaigns: org-scoped listing (INT-01 2.1 — GET /api/campaigns)
CREATE INDEX idx_campaigns_org_platform ON campaigns(organization_id, platform);
CREATE INDEX idx_campaigns_org_updated ON campaigns(organization_id, updated_at DESC);

-- campaigns: partial unique indexes for external_id vs CSV name (INT-01 1.2)
CREATE UNIQUE INDEX idx_campaigns_unique_external
    ON campaigns(data_source_id, external_id)
    WHERE external_id IS NOT NULL;

CREATE UNIQUE INDEX idx_campaigns_unique_name_csv
    ON campaigns(data_source_id, name)
    WHERE external_id IS NULL;

-- campaigns: data_source join optimization
CREATE INDEX idx_campaigns_data_source ON campaigns(data_source_id);

-- daily_metrics: org-scoped time-series (INT-01 3: no query without org_id)
CREATE INDEX idx_daily_metrics_org_date ON daily_metrics(organization_id, date DESC);

-- ga_events: org-scoped time-series
CREATE INDEX idx_ga_events_org_date ON ga_events(organization_id, date DESC);

-- feature_daily: org-scoped via entity_id lookup + date range
-- Note: entity_id = campaign_id for Month One; index supports AI Layer polling
CREATE INDEX idx_feature_daily_entity_date ON feature_daily(entity_id, metric_date DESC);

-- ==============================================================================
-- AI LAYER TABLES
-- ==============================================================================

-- model_runs: org-scoped status checks
CREATE INDEX idx_model_runs_org_status ON model_runs(organization_id, status, started_at DESC);

-- forecasts: campaign time-series (GET /api/campaigns/{id}/forecasts)
CREATE INDEX idx_forecasts_campaign_date ON forecasts(campaign_id, forecast_date);
CREATE INDEX idx_forecasts_model_run ON forecasts(model_run_id);
CREATE INDEX idx_forecasts_org ON forecasts(organization_id);

-- anomalies: campaign listing + severity filtering
CREATE INDEX idx_anomalies_campaign_detected ON anomalies(campaign_id, detected_at DESC);
CREATE INDEX idx_anomalies_model_run ON anomalies(model_run_id);
CREATE INDEX idx_anomalies_org ON anomalies(organization_id);

-- recommendations: org-scoped status filtering (GET /api/recommendations?organization_id=&status=)
CREATE INDEX idx_recommendations_org_status ON recommendations(organization_id, status, created_at DESC);
CREATE INDEX idx_recommendations_campaign ON recommendations(campaign_id);
CREATE INDEX idx_recommendations_model_run ON recommendations(model_run_id);
CREATE INDEX idx_recommendations_source_anomaly ON recommendations(source_anomaly_id) WHERE source_anomaly_id IS NOT NULL;

-- action_simulations: recommendation lookup
CREATE INDEX idx_action_sim_recommendation ON action_simulations(recommendation_id);

-- ==============================================================================
-- CONNECTOR TABLES
-- ==============================================================================

-- connector_tokens: refresh scheduling (find tokens nearing expiry)
CREATE INDEX idx_connector_tokens_expiry ON connector_tokens(expires_at)
    WHERE expires_at IS NOT NULL;

-- ==============================================================================
-- Schema Version
-- ==============================================================================
INSERT INTO schema_migrations (version, description)
VALUES ('006', 'Performance indexes and partial unique constraints')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS idx_users_email;
DROP INDEX IF EXISTS idx_org_members_org;
DROP INDEX IF EXISTS idx_org_members_user;
DROP INDEX IF EXISTS idx_data_sources_org_status;
DROP INDEX IF EXISTS idx_data_sources_provider_status;
DROP INDEX IF EXISTS idx_oauth_connections_org;
DROP INDEX IF EXISTS idx_jobs_queue_poll;
DROP INDEX IF EXISTS idx_jobs_model_run;
DROP INDEX IF EXISTS idx_jobs_org;
DROP INDEX IF EXISTS idx_exec_logs_org_time;
DROP INDEX IF EXISTS idx_exec_logs_recommendation;
DROP INDEX IF EXISTS idx_raw_api_idempotent;
DROP INDEX IF EXISTS idx_raw_api_data_source_fetched;
DROP INDEX IF EXISTS idx_campaigns_org_platform;
DROP INDEX IF EXISTS idx_campaigns_org_updated;
DROP INDEX IF EXISTS idx_campaigns_unique_external;
DROP INDEX IF EXISTS idx_campaigns_unique_name_csv;
DROP INDEX IF EXISTS idx_campaigns_data_source;
DROP INDEX IF EXISTS idx_daily_metrics_org_date;
DROP INDEX IF EXISTS idx_ga_events_org_date;
DROP INDEX IF EXISTS idx_feature_daily_entity_date;
DROP INDEX IF EXISTS idx_model_runs_org_status;
DROP INDEX IF EXISTS idx_forecasts_campaign_date;
DROP INDEX IF EXISTS idx_forecasts_model_run;
DROP INDEX IF EXISTS idx_forecasts_org;
DROP INDEX IF EXISTS idx_anomalies_campaign_detected;
DROP INDEX IF EXISTS idx_anomalies_model_run;
DROP INDEX IF EXISTS idx_anomalies_org;
DROP INDEX IF EXISTS idx_recommendations_org_status;
DROP INDEX IF EXISTS idx_recommendations_campaign;
DROP INDEX IF EXISTS idx_recommendations_model_run;
DROP INDEX IF EXISTS idx_recommendations_source_anomaly;
DROP INDEX IF EXISTS idx_action_sim_recommendation;
DROP INDEX IF EXISTS idx_connector_tokens_expiry;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
