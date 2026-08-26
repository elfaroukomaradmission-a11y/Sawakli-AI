"""AI Layer-owned tables

Ported from Ahmed Ibrahim's DATA-01 deliverable (004_ai_layer_tables.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0004_ai_layer_tables
Revises: 0003_data_layer_tables
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0004_ai_layer_tables"
down_revision = "0003_data_layer_tables"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 004: AI Layer-Owned Tables
-- ============================================
-- Purpose: Create the five tables owned exclusively by the AI Layer
-- per INT-01 Section 1.3.
--
-- Owner: AI Layer (sole logical writer).
-- Exception: Backend may UPDATE recommendations.status only (approval flow).
-- Build order: After 003 (depends on campaigns, organizations).
-- ============================================

-- ------------------------------------------------------------------------------
-- 1. model_runs
-- Split ownership lifecycle:
--   - Worker INSERTS the row (id, organization_id, triggered_by_user_id, started_at, status=RUNNING)
--   - AI Pipeline Orchestrator UPDATES status, campaigns_analyzed, error_message, completed_at
--
-- One ID travels the whole chain — Worker generates model_run_id first and
-- passes it into submit_job() per INT-01 Section 2.5.
-- ------------------------------------------------------------------------------
CREATE TABLE model_runs (
    id                  UUID PRIMARY KEY,               -- NOT DEFAULT — Worker mints this
    organization_id     UUID NOT NULL,
    triggered_by_user_id UUID,
    started_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status              model_run_status_enum NOT NULL DEFAULT 'RUNNING',
    campaigns_analyzed  JSONB,                          -- nullable until finalized
    error_message       TEXT,
    completed_at        TIMESTAMP,

    CONSTRAINT fk_model_runs_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_model_runs_triggered_by
        FOREIGN KEY (triggered_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON TABLE model_runs IS 'Pipeline execution audit trail. Split Worker/AI ownership. AI Layer-owned.';
COMMENT ON COLUMN model_runs.id IS 'Worker-generated UUID passed into AI Scheduler. One ID for the whole chain.';

-- ------------------------------------------------------------------------------
-- 2. forecasts
-- 7/14/30-day projections. One row per (campaign, metric, forecast_date).
-- "Horizon" is NOT a stored column — computed on read as (forecast_date - run_date).
-- ------------------------------------------------------------------------------
CREATE TABLE forecasts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_run_id    UUID NOT NULL,
    organization_id UUID NOT NULL,
    campaign_id     UUID NOT NULL,
    metric_name     VARCHAR NOT NULL,
    forecast_date   DATE NOT NULL,
    value           NUMERIC NOT NULL,
    ci_lower        NUMERIC,
    ci_upper        NUMERIC,
    model_used      VARCHAR,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_forecasts_model_run
        FOREIGN KEY (model_run_id) REFERENCES model_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_forecasts_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_forecasts_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

COMMENT ON TABLE forecasts IS '7/14/30-day projections. AI Layer-owned. Horizon computed at read time.';
COMMENT ON COLUMN forecasts.value IS 'Canonical name per INT-01 Section 4.2 (was: predicted_value).';
COMMENT ON COLUMN forecasts.ci_lower IS 'Confidence interval lower bound (was: confidence_low).';
COMMENT ON COLUMN forecasts.ci_upper IS 'Confidence interval upper bound (was: confidence_high).';

-- ------------------------------------------------------------------------------
-- 3. anomalies
-- No title/description/evidence columns here — UI-facing explanation comes from
-- the linked recommendation instead (INT-01 Section 4.2).
-- ------------------------------------------------------------------------------
CREATE TABLE anomalies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_run_id        UUID NOT NULL,
    organization_id     UUID NOT NULL,
    campaign_id         UUID NOT NULL,
    metric_name         VARCHAR NOT NULL,
    detected_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    anomaly_score       NUMERIC NOT NULL,
    severity            anomaly_severity_enum NOT NULL,
    direction           anomaly_direction_enum NOT NULL,
    detectors_triggered JSONB,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_anomalies_model_run
        FOREIGN KEY (model_run_id) REFERENCES model_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_anomalies_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_anomalies_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

COMMENT ON TABLE anomalies IS 'Anomaly detection output. AI Layer-owned. Explanation lives in linked recommendation.';
COMMENT ON COLUMN anomalies.metric_name IS 'Canonical name per INT-01 Section 4.2 (was: metric).';

-- ------------------------------------------------------------------------------
-- 4. recommendations
-- source_anomaly_id is nullable because opportunity-signal recommendations
-- (e.g., "increase budget") are not triggered by an anomaly at all.
-- problem doubles as the card title — no separate title column (INT-01 4.2).
-- ------------------------------------------------------------------------------
CREATE TABLE recommendations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_run_id        UUID NOT NULL,
    organization_id     UUID NOT NULL,
    campaign_id         UUID NOT NULL,
    source_anomaly_id   UUID,                           -- nullable FK → anomalies
    problem             TEXT NOT NULL,                  -- doubles as card title
    evidence            JSONB,
    suggested_action    TEXT,                           -- was: action
    confidence_score    NUMERIC,                        -- 0-1
    risk_rating         risk_rating_enum,
    severity            INT,                            -- 1-5 (DIFFERENT from anomalies.severity)
    status              recommendation_status_enum NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_recommendations_model_run
        FOREIGN KEY (model_run_id) REFERENCES model_runs(id) ON DELETE CASCADE,
    CONSTRAINT fk_recommendations_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_recommendations_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    CONSTRAINT fk_recommendations_source_anomaly
        FOREIGN KEY (source_anomaly_id) REFERENCES anomalies(id) ON DELETE SET NULL,

    -- INT-01 constraints
    CONSTRAINT chk_recommendations_confidence_range
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    CONSTRAINT chk_recommendations_severity_range
        CHECK (severity >= 1 AND severity <= 5)
);

COMMENT ON TABLE recommendations IS 'Recommendation engine output. AI Layer inserts; Backend updates status only.';
COMMENT ON COLUMN recommendations.problem IS 'Doubles as UI card title. No separate title column per INT-01 4.2.';
COMMENT ON COLUMN recommendations.suggested_action IS 'Canonical name per INT-01 4.2 (was: action).';
COMMENT ON COLUMN recommendations.confidence_score IS 'Canonical name per INT-01 4.2 (was: confidence).';
COMMENT ON COLUMN recommendations.risk_rating IS 'Canonical name per INT-01 4.2 (was: risk). lowercase in DB.';

-- ------------------------------------------------------------------------------
-- 5. action_simulations
-- Exactly 3 rows per recommendation, matching PROD-01's 3 scenarios:
--   - budget_decrease_20 (-20%)
--   - budget_increase_15 (+15%)
--   - pause
-- Values are always non-negative and internally consistent.
-- ------------------------------------------------------------------------------
CREATE TABLE action_simulations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id   UUID NOT NULL,
    scenario_type       simulation_scenario_enum NOT NULL,
    projected_spend     NUMERIC NOT NULL,
    projected_conversions NUMERIC NOT NULL,
    projected_cpa       NUMERIC NOT NULL,
    projected_roas      NUMERIC NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_action_simulations_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE,

    -- INT-01: values always non-negative
    CONSTRAINT chk_sim_spend_nonnegative
        CHECK (projected_spend >= 0),
    CONSTRAINT chk_sim_conversions_nonnegative
        CHECK (projected_conversions >= 0),
    CONSTRAINT chk_sim_cpa_nonnegative
        CHECK (projected_cpa >= 0),
    CONSTRAINT chk_sim_roas_nonnegative
        CHECK (projected_roas >= 0)
);

COMMENT ON TABLE action_simulations IS 'Exactly 3 rows per recommendation (-20%, +15%, pause). AI Layer-owned.';
COMMENT ON COLUMN action_simulations.scenario_type IS 'Locked to 3 scenarios per PROD-01.';

-- ------------------------------------------------------------------------------
-- Schema Version
-- ------------------------------------------------------------------------------
INSERT INTO schema_migrations (version, description)
VALUES ('004', 'AI Layer-owned tables')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS action_simulations;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS anomalies;
DROP TABLE IF EXISTS forecasts;
DROP TABLE IF EXISTS model_runs;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
