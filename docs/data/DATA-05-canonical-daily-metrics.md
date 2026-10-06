# DATA-05 — Canonical Daily Metrics & GA Event Normalization

## 1. Overview

This task implements the canonical time-series fact layer for campaign-day metrics consumed by the Backend and AI layers. It normalizes raw daily marketing totals into the same shape defined by the INT-01 data contract and ensures the values are safe for downstream analytics and feature engineering.

Before this task, the repository had the schema for `daily_metrics` and `ga_events`, but it lacked the actual normalization layer that converts staged source data into canonical rows. This task closes that gap by adding the missing validation and normalization boundary for campaign-day metrics and GA event aggregates.

## 2. Scope

### In Scope

- Normalization of campaign-day metric rows into the canonical daily metric contract
- Normalization of GA event aggregate rows into the canonical GA event contract
- Strict date parsing and numeric validation for currency and count values
- Safe handling of optional GA fields such as `bounces` and `session_duration`
- Exposing the normalized payloads and staging contracts for reuse by ingestion or later pipeline steps
- Regression tests proving the normalization behavior is stable

### Out of Scope

- Writing a full ingestion job or storage pipeline for external providers
- Creating new database migrations or altering table ownership contracts
- Introducing a second persistence abstraction or AI-specific feature cache
- Implementing replay or backfill orchestration for historical demo loads

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| INT-01 Canonical MVP Contract Pack | Defines the canonical schema and non-negativity expectations for `daily_metrics` and `ga_events` |
| DATA-01 schema migrations | Establish the live `daily_metrics` and `ga_events` tables and their constraints |
| DATA-04 entity normalization | Provides the surrounding staging and normalization pattern for campaign-ad entity identity |
| `apps/backend/alembic/versions/0003_data_layer_tables.py` | Source of the implemented database contract used in this task |
| `tests/contracts/canonical.json` | Operational contract reference for canonical entity semantics |

## 4. Architecture

The task sits in the Data layer, between staged source rows and the persistent canonical tables.

```text
Staged source row
    ↓
Data normalization layer
    ↓
Canonical payload (daily_metrics / ga_events)
    ↓
Database read/write boundary
    ↓
Backend / AI consumers
```

Ownership boundaries:

- Data Layer owns the staging and normalization model for raw metric rows.
- Backend owns the canonical database contract used by application queries.
- AI reads the canonical facts as its source of truth and does not create a duplicate metric copy.
- This task does not broaden ownership beyond the Data layer contract.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `date` | string | Yes | staged metric / GA event payload | ISO date in `YYYY-MM-DD` format |
| `spend` | string | Yes for daily metrics | staged metric payload | Non-negative numeric value |
| `impressions` | string | Yes for daily metrics | staged metric payload | Non-negative integer |
| `clicks` | string | Yes for daily metrics | staged metric payload | Non-negative integer |
| `conversions` | string | Yes for daily metrics | staged metric payload | Non-negative integer |
| `revenue` | string | Yes for daily metrics | staged metric payload | Non-negative numeric value |
| `sessions` | string or null | No for GA events | staged GA payload | Non-negative integer, defaults to `0` when absent |
| `bounces` | string or null | No for GA events | staged GA payload | Non-negative integer, must not exceed sessions |
| `session_duration` | string or null | No | staged GA payload | Optional numeric field retained as nullable |
| `campaign_id` | UUID | Yes | caller / normalized campaign identity | Must belong to the target organization |
| `organization_id` | UUID | Yes | caller / tenant context | Enforced as the owning organization |

Validation behavior:

- ISO dates are parsed strictly.
- Negative values are rejected.
- Non-integer values for integer fields are rejected.
- `bounces > sessions` is rejected.
- Null or blank optional GA values are normalized to safe zero/nullable defaults.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `DailyMetricUpsertPayload` | dataclass | No | Data pipeline | Canonical normalized daily metric row |
| `GAEventUpsertPayload` | dataclass | No | Data pipeline | Canonical normalized GA event aggregate row |
| `organization_id` | UUID | No | Backend / AI | Tenant ownership |
| `campaign_id` | UUID | No | Backend / AI | Campaign identity |
| `date` | date | No | Backend / AI | Campaign-day key |
| `spend` | float | No | Backend / AI | Canonical spend fact |
| `impressions` | int | No | Backend / AI | Canonical impression fact |
| `clicks` | int | No | Backend / AI | Canonical click fact |
| `conversions` | int | No | Backend / AI | Canonical conversion fact |
| `revenue` | float | No | Backend / AI | Canonical revenue fact |
| `sessions` | int | No | Backend / AI | Canonical GA session count |
| `bounces` | int | No | Backend / AI | Canonical GA bounce count |
| `session_duration` | float | Yes | Backend / AI | Optional GA duration fact |

## 7. Rules and Semantics

The canonical contract follows the database schema defined in the migration files and enforced by the INT-01 rules:

- `daily_metrics` stores five raw facts only: `spend`, `clicks`, `impressions`, `conversions`, `revenue`.
- Ratios such as CTR, CPC, CPA, and ROAS are computed at read time rather than stored.
- `ga_events` stores `sessions` and `bounces` as the campaign-day aggregate for bounce-rate KPI work.
- `session_duration` remains schema-present but nullable, matching the CSV and demo-data contract.
- `bounces <= sessions` is a hard invariant.
- All raw facts are non-negative.
- Every row is keyed by `(campaign_id, date)` for the canonical table grain.

This task does not invent a different metric semantics model. It preserves the project’s existing data ownership and naming conventions from the declared schema contract.

## 8. Public Interfaces

The meaningful public interfaces implemented by this task are the normalization functions and the staging models exposed under the Data layer.

### `normalize_daily_metric(...)`

- Input: `StagedDailyMetricRow`, `campaign_id`, `organization_id`
- Output: `DailyMetricUpsertPayload`
- Behavior: validates and parses the date and numeric values into the canonical tuple for a daily metric row
- Errors: raises a `ValueError` for malformed dates

### `normalize_ga_event(...)`

- Input: `StagedGAEventRow`, `campaign_id`, `organization_id`
- Output: `GAEventUpsertPayload`
- Behavior: validates and parses the GA aggregate values and applies the canonical defaults for missing optional inputs
- Errors: raises a `ValueError` for malformed dates

### `StagedDailyMetricRow`

- Represents the raw staged daily metric values before canonical normalization.

### `StagedGAEventRow`

- Represents the raw staged GA event aggregate values before canonical normalization.

## 9. Data Ownership

### Reads

- Reads source rows from the staged input representation used by the Data layer.
- Reads the canonical table definitions for `daily_metrics` and `ga_events` from the shared schema contract.

### Writes

- Writes canonical normalized rows to the Data layer’s payload model and downstream persistence boundary.
- This task does not write directly to production tables in the repo code path; it produces the canonical payloads expected by the persistence layer.

### Must Never Read

- No user PII or raw user profile data is part of this task.
- No unscoped cross-tenant data is read here.

### Must Never Write

- This task does not write to AI feature tables or recommendation tables.
- It does not mutate campaign ownership, authorization state, or connector tokens.

## 10. Security

This task keeps the previous project security posture in place:

- Organization scope is preserved by carrying `organization_id` into every canonical payload.
- The task does not inspect or expose rows outside the tenant context.
- No secrets, OAuth tokens, or personal account data are introduced.
- The code does not log or return sensitive values.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Missing input | A malformed or incomplete staged row is rejected by validation before reaching the canonical payload |
| Malformed input | Invalid date strings raise a `ValueError` for the normalization function |
| Zero values | Zero is accepted and preserved as a valid fact |
| Insufficient data | Optional GA inputs fall back to zero or `None` as appropriate |
| Duplicate records | The canonical table contract prohibits duplicates by `(campaign_id, date)` and downstream persistence should enforce it |
| Database failure | The task itself is validation-only; the persistence layer owns database-level failures |
| Provider or API failure | Not applicable to this local normalization contract |
| Timeout | Not applicable to this pure validation / transformation code path |
| Cancellation | Not applicable to this synchronous normalization step |

## 12. Testing

### Unit Tests

The regression coverage added in this task verifies:

- `normalize_campaign()` still behaves as expected
- `normalize_daily_metric()` parses the canonical monetary and count fields correctly
- `normalize_ga_event()` parses the GA aggregate fields and handles optional GA values safely
- Domain invariant checking is preserved for the metric fields and GA bounce/session relationship

### Integration Tests

No new real PostgreSQL integration test was added for this task because the repo’s existing integration suite is environment-dependent and the task scope here is the canonical normalization boundary itself. The repository already includes schema-level and data-layer fixtures that define the contract.

### E2E Impact

No direct E2E impact was introduced. The change is a data-layer normalization improvement that supports downstream analytics and AI feature pipelines.

## 13. Verification

Commands executed:

```bash
cd "D:/projects/Sawakli-AI/apps/backend"; & "C:/Users/cairo/AppData/Local/Programs/Python/Python314/python.exe" -m pytest tests/unit/data/normalization/test_normalize.py -q
```

Result:

- Status: PASS
- Evidence: `6 passed` in `0.08s`
- Environment: local Windows backend environment with the repo’s Python dependencies installed

## 14. Known Limitations

- This task implements the canonical normalization contract but does not yet add a production ingestion job that writes these canonical rows from live provider payloads.
- The GA event contract is normalized at the aggregate campaign/day level as defined by the schema, not at a session-level event-log grain.
- The current test coverage validates the normalization boundary rather than full end-to-end provider ingestion.

## 15. Follow-Up Tasks

- None required for the immediate normalization contract itself.
- Recommended follow-up: implement the actual ingestion pipeline that stages and writes `daily_metrics` and `ga_events` from source data under the same canonical rules.

## 16. References and Evidence

- Canonical schema: `apps/backend/alembic/versions/0003_data_layer_tables.py`
- Canonical contract checks: `tests/contracts/canonical.json`
- Implementation: `apps/backend/src/sawakli/data/normalization/normalize.py`
- Payload model: `apps/backend/src/sawakli/data/normalization/payloads.py`
- Staging model: `apps/backend/src/sawakli/data/staging/models.py`
- Regression tests: `apps/backend/tests/unit/data/normalization/test_normalize.py`

This task is implemented and validated at the canonical normalization boundary for campaign-day metrics and GA event aggregates.
