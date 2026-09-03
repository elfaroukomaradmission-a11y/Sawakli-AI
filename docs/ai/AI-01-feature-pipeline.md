# AI-01 Data Access and Feature Pipeline

## Purpose

AI-01 is the stable, deterministic, organization-scoped input boundary for later AI tasks. It
loads campaign-day facts and computes descriptive historical features. It does not persist
features or perform anomaly detection, forecasting, recommendations, simulation, or orchestration.

The current AI pipeline reads `daily_metrics` and organization-matched `campaigns`. It does not
read the legacy `feature_daily` table. Feature calculations are owned by `sawakli.ai.features`.

## Typed input contract

Both loaders return an ordered `tuple[MetricRecord, ...]`. Each record contains:

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `organization_id` | UUID | yes | Explicit tenant boundary |
| `campaign_id` | UUID | yes | Stable campaign identity |
| `campaign_name` | string | yes | Campaign metadata |
| `platform` | `meta` or `google` | yes | Campaign metadata |
| `date` | date | yes | Observation date |
| `spend`, `revenue` | Decimal | yes | Non-negative raw facts |
| `impressions`, `clicks`, `conversions` | integer | yes | Non-negative raw facts |
| `sessions`, `bounces` | integer or `None` | no | Optional analytics facts |
| `session_duration` | Decimal or `None` | no | Reserved optional analytics fact |

`Decimal` is used instead of binary floating point. Output is sorted by campaign UUID and date.
Duplicate campaign/date observations are rejected.

## Loading modes

### Database

`DatabaseDataLoader(session).load_metrics(organization_id, campaign_ids, date_from, date_to)` uses
the existing synchronous SQLAlchemy `Session` and query-only Core table definitions. Every query
filters both `daily_metrics.organization_id` and `campaigns.organization_id`, and joins the two on
both campaign ID and organization ID. A foreign campaign ID in `campaign_ids` therefore returns no
foreign rows. Results are ordered in SQL by campaign ID and date.

Known follow-up: the historical security migration grants `ai_layer_role` access to `daily_metrics`
and `campaigns`, but not `ga_events`. AI-01 does not change permissions or historical migrations, so
database-mode optional GA fields are currently `None`. The permission mismatch must be resolved in
a separate task before the AI database path can consume session/bounce facts.

### Local CSV

`CsvDataLoader(path, campaign_id_map=...)` accepts a caller-supplied path. Required columns are:

`date,campaign_name,platform,spend,impressions,clicks,conversions,revenue`

`sessions` and `bounces` are optional. Missing optional values remain `None`; they are not converted
to measured zeros. The loader validates the entire file and raises `FeatureDataError` with the row
and field when input is malformed.

The optional map is keyed by `(campaign_name, platform)`. Without a mapping, local IDs are UUIDv5
values derived from organization ID, normalized platform, and campaign name. They are stable across
runs and tenants and never random. Callers can obtain the same value with `local_campaign_id(...)`.

## Feature definitions

All ratios use the same `safe_divide` primitive and a pinned 28-digit, half-even Decimal context.

| Output | Formula |
|---|---|
| `ctr` | `clicks / impressions` |
| `cpc` | `spend / clicks` |
| `cpa` | `spend / conversions` |
| `roas` | `revenue / spend` |
| `bounce_rate` | `bounces / sessions`, when both inputs exist |
| `rolling_ctr_7d`, `rolling_ctr_14d` | `sum(window clicks) / sum(window impressions)` |
| `rolling_cpc_7d`, `rolling_cpc_14d` | `sum(window spend) / sum(window clicks)` |
| `spend_trend` | `(today spend - yesterday spend) / yesterday spend` |
| `conversion_trend` | `(today conversions - yesterday conversions) / yesterday conversions` |
| `roas_trend` | `(today ROAS - yesterday ROAS) / yesterday ROAS` |

`ROLLING_WINDOWS = (7, 14)` is the central window declaration. The rolling implementation itself is
window-parameterized.

## Missing values and history semantics

`None` is the only missing-value representation. Division by zero returns `None`; it never returns
zero or infinity. Rolling CTR and CPC are ratios of aggregated raw facts, not arithmetic means of
daily ratios. A rolling result is available only when the campaign has one observation for each
calendar day in the complete window. A zero aggregated denominator produces `None`; an individual
day with a zero denominator does not invalidate the window when the aggregated denominator is
positive. Early rows and rows after a gap are preserved with unavailable rolling values set to
`None`.

Trend fields are day-over-day fractional changes: `(today - previous_day) / previous_day`. The first
campaign row, a row following a date gap, an unavailable previous value, a zero previous value, or an
undefined current/previous ROAS produces `None` for the affected trend.

All records are sorted before calculation and grouped by campaign. No rolling or trend state can
cross campaign boundaries.

## Output example

For spend `100`, impressions `1,000`, clicks `50`, conversions `5`, revenue `300`, sessions `400`,
and bounces `100`, the base output is CTR `0.05`, CPC `2`, CPA `20`, ROAS `3`, and bounce rate `0.25`.
If this is the first observation, every rolling and trend field is `None`; the row is still returned.

## Explicit exclusions

AI-01 does not implement or invent an `anomaly_score_input`; z-scores, IQR, Isolation Forest,
forecasting models, recommendations, confidence scores, simulation logic, and pipeline orchestration
belong to AI-02 through AI-06. AI-01 does not write to `daily_metrics`, create a feature cache, depend
on `feature_daily`, or modify historical migrations.
