"""Data Layer-owned tables

Ported from Ahmed Ibrahim's DATA-01 deliverable (003_data_layer_tables.sql), run and
verified against a real PostgreSQL 16 instance before conversion — see
DATA-01 reconciliation notes. The SQL below is byte-for-byte identical to
the original file; only the execution mechanism changed (raw DBAPI cursor,
see sawakli/db/migration_utils.py) so this runs correctly under Alembic instead of
via `psql -f` / docker-entrypoint-initdb.d.

Revision ID: 0003_data_layer_tables
Revises: 0002_backend_tables
"""

from __future__ import annotations

from sawakli.db.migration_utils import execute_sql_script

# revision identifiers, used by Alembic.
revision = "0003_data_layer_tables"
down_revision = "0002_backend_tables"
branch_labels = None
depends_on = None

_UPGRADE_SQL = r"""
-- ============================================
-- MIGRATION 003: Data Layer-Owned Tables
-- ============================================
-- Purpose: Create the eight tables owned exclusively by the Data Layer
-- per INT-01 Section 1.2.
--
-- Owner: Data Layer (sole logical writer).
-- Read access: AI Layer (read-only, org-scoped), Backend (read-only, org-scoped).
-- Build order: After 002 (depends on organizations, data_sources).
-- ============================================

-- ------------------------------------------------------------------------------
-- 1. raw_api_responses
-- Immutable, provider-faithful copy of every pull.
-- Idempotent insert keyed on (data_source_id, endpoint, fetched_at).
-- ------------------------------------------------------------------------------
CREATE TABLE raw_api_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id  UUID NOT NULL,
    provider        provider_enum NOT NULL,
    endpoint        TEXT NOT NULL,
    payload         JSONB,
    fetched_at      TIMESTAMP NOT NULL,

    CONSTRAINT fk_raw_api_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
);

COMMENT ON TABLE raw_api_responses IS 'Immutable provider-faithful copy. Data Layer-owned. Idempotent on (data_source_id, endpoint, fetched_at).';

-- ------------------------------------------------------------------------------
-- 2. campaigns
-- organization_id and platform are denormalized directly onto this row so
-- every query can filter or join on them without going through data_sources.
-- data_source_id is NEVER null — CSV/demo campaigns still point to a data_sources row.
--
-- Uniqueness:
--   - (data_source_id, external_id) when external_id is present
--   - (data_source_id, name) for CSV rows (no external_id)
-- ------------------------------------------------------------------------------
CREATE TABLE campaigns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    data_source_id  UUID NOT NULL,
    external_id     TEXT,                           -- nullable for CSV/demo
    name            TEXT NOT NULL,
    platform        platform_enum NOT NULL,
    objective       TEXT,
    status          campaign_status_enum,
    budget          NUMERIC,
    start_date      DATE,
    end_date        DATE,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_campaigns_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_campaigns_data_source
        FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
);

COMMENT ON TABLE campaigns IS 'Campaign grain for Month One. Data Layer-owned. org_id and platform denormalized for query performance.';
COMMENT ON COLUMN campaigns.external_id IS 'Nullable for CSV/demo sources. Uniqueness handled by partial indexes in Migration 006.';

-- ------------------------------------------------------------------------------
-- 3. ad_groups
-- Schema present for completeness; NOT populated by Month-One CSV path.
-- ------------------------------------------------------------------------------
CREATE TABLE ad_groups (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL,
    external_id TEXT,
    name        TEXT,
    status      campaign_status_enum,

    CONSTRAINT fk_ad_groups_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

COMMENT ON TABLE ad_groups IS 'Schema completeness only. Not populated by Month-One demo path. Data Layer-owned.';

-- ------------------------------------------------------------------------------
-- 4. ads
-- Schema present for completeness; NOT populated by Month-One CSV path.
-- ------------------------------------------------------------------------------
CREATE TABLE ads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_group_id UUID NOT NULL,
    external_id TEXT,
    name        TEXT,
    status      campaign_status_enum,

    CONSTRAINT fk_ads_ad_group
        FOREIGN KEY (ad_group_id) REFERENCES ad_groups(id) ON DELETE CASCADE
);

COMMENT ON TABLE ads IS 'Schema completeness only. Not populated by Month-One demo path. Data Layer-owned.';

-- ------------------------------------------------------------------------------
-- 5. creatives
-- Schema present for completeness; NOT populated by Month-One CSV path.
-- ------------------------------------------------------------------------------
CREATE TABLE creatives (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id         UUID NOT NULL,
    creative_type VARCHAR,
    headline      TEXT,
    asset_url     TEXT,

    CONSTRAINT fk_creatives_ad
        FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE
);

COMMENT ON TABLE creatives IS 'Schema completeness only. Not populated by Month-One demo path. Data Layer-owned.';

-- ------------------------------------------------------------------------------
-- 6. daily_metrics
-- 5 raw facts only — NO stored ratios (CTR, CPC, CPA, ROAS).
-- Those are computed at read time, everywhere.
-- Campaign-grain only for Month One.
-- organization_id is denormalized directly for org-scoping and indexing.
-- Unique on (campaign_id, date).
-- ------------------------------------------------------------------------------
CREATE TABLE daily_metrics (
    organization_id UUID NOT NULL,
    campaign_id     UUID NOT NULL,
    date            DATE NOT NULL,
    spend           NUMERIC NOT NULL DEFAULT 0,
    clicks          INT NOT NULL DEFAULT 0,
    impressions     INT NOT NULL DEFAULT 0,
    conversions     INT NOT NULL DEFAULT 0,
    revenue         NUMERIC NOT NULL DEFAULT 0,

    PRIMARY KEY (campaign_id, date),

    CONSTRAINT fk_daily_metrics_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    CONSTRAINT fk_daily_metrics_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,

    -- INT-01: all raw facts are non-negative
    CONSTRAINT chk_daily_metrics_spend_nonnegative
        CHECK (spend >= 0),
    CONSTRAINT chk_daily_metrics_clicks_nonnegative
        CHECK (clicks >= 0),
    CONSTRAINT chk_daily_metrics_impressions_nonnegative
        CHECK (impressions >= 0),
    CONSTRAINT chk_daily_metrics_conversions_nonnegative
        CHECK (conversions >= 0),
    CONSTRAINT chk_daily_metrics_revenue_nonnegative
        CHECK (revenue >= 0)
);

COMMENT ON TABLE daily_metrics IS '5 raw facts only — ratios computed at read time. Campaign-grain for Month One. Data Layer-owned.';

-- ------------------------------------------------------------------------------
-- 7. ga_events
-- Campaign + day aggregate grain, matching the bounce-rate KPI locked in PROD-01.
-- Per-session event log would need its own table name if built later.
-- session_duration is schema-present but NOT populated by the CSV path.
-- ------------------------------------------------------------------------------
CREATE TABLE ga_events (
    organization_id     UUID NOT NULL,
    campaign_id         UUID NOT NULL,
    date                DATE NOT NULL,
    sessions            INT NOT NULL DEFAULT 0,
    bounces             INT NOT NULL DEFAULT 0,
    session_duration    NUMERIC,                    -- nullable, not populated by CSV

    PRIMARY KEY (campaign_id, date),

    CONSTRAINT fk_ga_events_campaign
        FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
    CONSTRAINT fk_ga_events_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,

    -- INT-01: bounces <= sessions
    CONSTRAINT chk_ga_events_sessions_nonnegative
        CHECK (sessions >= 0),
    CONSTRAINT chk_ga_events_bounces_nonnegative
        CHECK (bounces >= 0),
    CONSTRAINT chk_ga_events_bounces_lte_sessions
        CHECK (bounces <= sessions)
);

COMMENT ON TABLE ga_events IS 'Campaign+day aggregate for bounce-rate KPI. Data Layer-owned. session_duration schema-present but CSV-unpopulated.';

-- ------------------------------------------------------------------------------
-- 8. feature_daily
-- Canonical feature source — AI Layer reads this directly instead of keeping
-- its own copy (feature_cache removed from Month-One schema per INT-01 1.3).
-- Insufficient-history rows are represented explicitly (nullable fields),
-- never silently omitted.
-- ------------------------------------------------------------------------------
CREATE TABLE feature_daily (
    entity_id           UUID NOT NULL,              -- = campaign_id for Month One
    metric_date         DATE NOT NULL,
    rolling_ctr_7d      NUMERIC,
    rolling_ctr_14d     NUMERIC,
    rolling_cpc_7d      NUMERIC,
    rolling_cpc_14d     NUMERIC,
    spend_trend         NUMERIC,
    conversion_trend    NUMERIC,
    roas_trend          NUMERIC,
    anomaly_score_input NUMERIC,

    PRIMARY KEY (entity_id, metric_date),

    CONSTRAINT fk_feature_daily_entity
        FOREIGN KEY (entity_id) REFERENCES campaigns(id) ON DELETE CASCADE
);

COMMENT ON TABLE feature_daily IS 'Canonical feature source. AI Layer reads directly — no separate feature_cache. Data Layer-owned.';
COMMENT ON COLUMN feature_daily.entity_id IS 'campaign_id for Month One. Polymorphic door open for future phases.';

-- ------------------------------------------------------------------------------
-- Schema Version
-- ------------------------------------------------------------------------------
INSERT INTO schema_migrations (version, description)
VALUES ('003', 'Data Layer-owned tables')
ON CONFLICT (version) DO NOTHING;

"""

_DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS feature_daily;
DROP TABLE IF EXISTS ga_events;
DROP TABLE IF EXISTS daily_metrics;
DROP TABLE IF EXISTS creatives;
DROP TABLE IF EXISTS ads;
DROP TABLE IF EXISTS ad_groups;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS raw_api_responses;
"""


def upgrade() -> None:
    execute_sql_script(_UPGRADE_SQL)


def downgrade() -> None:
    execute_sql_script(_DOWNGRADE_SQL)
