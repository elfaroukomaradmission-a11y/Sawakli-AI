# QA-02 — Run Connector-to-Canonical Data Pipeline E2E Test

## 1. Overview

This task verifies the CSV connector path from a seeded provider payload through raw persistence, CSV parsing, staging, campaign normalization, canonical daily metrics, and GA event aggregates.

The test proves the path used by the demo connector produces reconciled canonical facts, is idempotent when the same source rows are imported again, and reports malformed row failures without presenting invalid data as canonical success.

Status: **Implemented and verified** for the CSV/demo path. The GA4-shaped aggregate path is included through the canonical `ga_events` contract using the sessions and bounces fields available in the CSV input. A live external GA4 provider call is out of scope for this repository test.

## 2. Scope

### In Scope

- Seed one CSV payload into `raw_api_responses`
- Parse the seeded CSV through `parse_csv_upload`
- Preserve valid rows and report malformed rows as parse warnings
- Adapt valid rows into staging models
- Normalize and upsert campaigns, daily metrics, and GA event aggregates
- Re-import the same rows and prove no duplicate campaigns, daily metrics, or GA events remain
- Reconcile canonical totals against hand-calculable source totals
- Verify the canonical GA event aggregate path for sessions and bounces
- Clean up all organization-scoped test data after the test

### Out of Scope

- Calling an external Meta, Google Ads, or GA4 provider
- OAuth authorization and token refresh
- Background job orchestration or scheduling
- Frontend upload transport
- Feature engineering, anomaly detection, forecasts, or recommendations
- Replacing the canonical database contract

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| CONN-01 | Defines the connector CSV parser and connector error behavior |
| DATA-03 | Defines raw provider response persistence and source ownership |
| DATA-04 | Defines campaign identity and idempotent entity normalization |
| DATA-05 | Defines canonical daily metric and GA event normalization |
| INT-01 / canonical data contract | Defines campaign-day grain, non-negative facts, and organization scope |
| PostgreSQL test database | Required for migrations, constraints, upserts, and reconciliation queries |

## 4. Architecture

```text
Seeded CSV bytes
      ↓
CSV connector parser
      ↓
raw_api_responses (immutable source evidence)
      ↓
StagedCampaignRow + metric/event facts
      ↓
Campaign normalization and upsert
      ↓
DailyMetricUpsertPayload / GAEventUpsertPayload
      ↓
daily_metrics + ga_events
      ↓
Reconciliation and duplicate checks
```

Ownership boundaries:

- Connector owns decoding, CSV shape validation, and row-level parse warnings.
- Data owns staging, normalization, canonical upserts, organization scope, and reconciliation facts.
- PostgreSQL owns primary keys, foreign keys, non-negative checks, and campaign-day uniqueness.
- The test owns setup and teardown only; it does not create a competing schema or persistence layer.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| CSV payload | UTF-8 text | Yes | Seeded test fixture | Contains campaign-day metrics and optional sessions/bounces |
| `organization_id` | UUID | Yes | Test fixture | Tenant scope for every inserted row |
| `data_source_id` | UUID | Yes | Test fixture | CSV demo source identity |
| `upload_id` | UUID | Yes | Test fixture | Raw response identity |
| `date` | ISO date | Yes | CSV | Canonical campaign-day key |
| `campaign_name` | string | Yes | CSV | Fallback campaign identity for CSV rows |
| `platform` | `meta` or `google` | Yes | CSV | Canonical platform mapping input |
| metric fields | numeric strings | Yes | CSV | Spend, impressions, clicks, conversions, revenue |
| GA aggregate fields | numeric strings | Optional | CSV | Sessions and bounces; blanks default to zero |

The fixture contains four valid rows, one malformed numeric row, and one repeated valid row. The malformed row is not forwarded into staging. The repeated valid row tests idempotency at the canonical campaign-day grain.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| raw source row | PostgreSQL row | No | Data / audit | One immutable `raw_api_responses` record |
| parsed rows | `RawResponse` | No | Staging | Four valid rows and one parse warning |
| campaign rows | PostgreSQL rows | No | Backend / AI | Two unique campaigns |
| daily metrics | PostgreSQL rows | No | Backend / AI | Three unique campaign-day metric rows |
| GA events | PostgreSQL rows | No | Backend / AI | Three unique campaign-day GA aggregate rows |
| reconciliation totals | SQL aggregates | No | QA evidence | Spend, impressions, clicks, conversions, revenue, sessions, bounces |

Expected reconciliation:

- Daily metrics: `(spend, impressions, clicks, conversions, revenue) = (225, 2250, 225, 23, 450)`
- GA events: `(sessions, bounces) = (1200, 240)`
- Campaign count: `2`
- Daily metric count: `3`
- GA event count: `3`
- Raw response count: `1`

## 7. Rules and Semantics

- The CSV parser rejects invalid file-level inputs and skips malformed individual rows with warnings.
- Only rows accepted by the connector parser enter the staging/normalization path.
- CSV campaigns have no external ID; identity falls back to data source, campaign name, and platform.
- Canonical metric and GA event identity is `(campaign_id, date)`.
- Re-importing an identical source row updates the existing canonical row rather than inserting a duplicate.
- Canonical totals must equal the sum of the valid source rows, excluding the malformed row.
- Sessions and bounces are carried into `ga_events`; the database constraint enforces `bounces <= sessions`.
- Every query and write in the test is organization-scoped.
- The test uses deterministic fixture values and UUIDs generated per test run to avoid cross-test collisions.

## 8. Public Interfaces

### `parse_csv_upload(file_stream, org_id, upload_id)`

Reads the CSV stream and returns `RawResponse` on partial/full parse success or `ConnectorError` on file-level failure. It performs no persistence itself.

### `staged_row_from_csv_dict(organization_id, data_source_id, parsed_row)`

Maps a valid parsed CSV row into a `StagedCampaignRow`, including the daily metric and GA event facts used by the normalization pipeline.

### `normalize_and_upsert_batch(db, rows)`

Normalizes and persists campaign entities, daily metrics, and GA event aggregates. Repeated campaign-day rows use database upsert semantics.

### E2E test

`tests/integration/data/test_connector_to_canonical_e2e.py::test_csv_connector_reaches_canonical_facts_with_reconciliation`

Creates its own source records, executes the complete path, asserts reconciliation and deduplication, then deletes its organization to clean up dependent data.

## 9. Data Ownership

### Reads

- Reads the seeded CSV stream through the Connector parser.
- Reads canonical tables through organization-scoped SQL aggregate queries.

### Writes

- Writes one test-scoped `raw_api_responses` row.
- Writes test-scoped organization, data source, campaigns, daily metrics, and GA events through the established database boundaries.

### Must Never Read

- Another organization’s raw payloads or canonical facts.
- Provider secrets, OAuth tokens, or external credentials.

### Must Never Write

- Data outside the generated test organization.
- Production records or shared demo records.
- Duplicate canonical rows for the same campaign-day key.

## 10. Security

- The test uses a generated organization UUID and synthetic payload only.
- All test queries include the generated organization or data source scope.
- No real credentials, tokens, personal data, or external provider calls are used.
- Cleanup removes the generated organization, cascading its dependent source and canonical rows.
- The canonical database constraints remain the enforcement boundary for organization isolation and valid metric values.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Empty CSV or invalid header | Connector returns a typed `ConnectorError`; no canonical rows are created |
| Malformed metric row | Row is skipped and a parse warning identifies the row and reason |
| Negative or non-numeric values | Row is rejected before staging |
| Duplicate valid row | Upsert updates the existing campaign-day row; counts remain unchanged |
| Invalid canonical invariant | PostgreSQL constraint rejects the write, such as `bounces > sessions` |
| Database failure | Test fails rather than presenting partial success as a passing reconciliation |
| External provider failure | Not exercised; no live provider call is made |
| Timeout | Not applicable to this deterministic local integration test |
| Cancellation | Test runner cancellation leaves the standard test database teardown responsibility |

## 12. Testing

### Unit Tests

The existing connector parser and normalization unit tests remain relevant for field-level validation and typed payload conversion.

### Integration Tests

The new QA-02 test runs against the migrated PostgreSQL test database and verifies:

- Raw persistence exists before canonical processing.
- Four valid rows survive parsing and one malformed row is reported.
- Campaign, daily metric, and GA event rows are produced.
- Source totals reconcile exactly with canonical totals.
- Re-importing the same batch leaves counts and returned campaign IDs stable.
- Generated test data is removed after the test.

### E2E Impact

This is the backend data-path E2E evidence for the CSV/demo connector. A live GA4 E2E test remains deferred until an external-provider fixture or approved connector replay fixture is available.

## 13. Verification

Command executed:

```powershell
cd "D:/projects/Sawakli-AI/apps/backend"; & "C:/Users/cairo/AppData/Local/Programs/Python/Python314/python.exe" -m pytest tests/integration/data/test_connector_to_canonical_e2e.py -q
```

Result:

- `PASS` — `1 passed` in `1.15s`
- Database: migrated PostgreSQL test database on the repository test service
- Reconciliation: passed with the expected metric and GA totals documented in Section 6
- Warnings: 5 dependency/schema warnings were emitted; none caused test failure

An earlier direct run of the pre-existing DATA-04 test file was `NOT RUN — test database schema unavailable` because it bypassed the repository migration fixture and pointed at an uninitialized test database. The QA-02 test uses the shared migrated-database fixture and passed.

## 14. Known Limitations

- The test uses a deterministic CSV fixture rather than a live provider network call.
- The current connector parser is the tested CSV path; live GA4 provider authorization and ingestion are not available in this test surface.
- The raw response write is seeded directly in the test because no production CSV upload API/application workflow currently owns that write.
- Full backend quality gates were not rerun for this task; the focused E2E test is the recorded verification evidence.

## 15. Follow-Up Tasks

- CONN-02 — Connector owner — connect the frontend CSV upload to raw persistence and this parser/pipeline boundary.
- CONN-GA4 — Connector owner — add a replayable GA4 fixture and provider-to-raw test when the GA4 connector contract is available.
- DATA-PIPELINE — Data owner — expose the production ingestion job that invokes this pipeline rather than test-seeding raw persistence.

## 16. References and Evidence

- Connector parser: `apps/backend/src/sawakli/connectors/csv/parser.py`
- Staging adapter: `apps/backend/src/sawakli/data/staging/adapters.py`
- Normalization pipeline: `apps/backend/src/sawakli/data/normalization/pipeline.py`
- Canonical upserts: `apps/backend/src/sawakli/data/normalization/upsert.py`
- E2E test: `apps/backend/tests/integration/data/test_connector_to_canonical_e2e.py`
- Canonical schema: `apps/backend/alembic/versions/0003_data_layer_tables.py`
- Evidence: `1 passed` focused pytest run above
- Screenshot evidence: `N/A — backend data pipeline task`
