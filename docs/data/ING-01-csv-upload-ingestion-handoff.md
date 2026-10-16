# ING-01 — Implement Data-Owned CSV Upload Ingestion Handoff

## 1. Overview

**Status:** Implemented
**Owner:** Data Layer
**Deadline:** Thu 15 Oct 23:59 Africa/Cairo (2026-10-15)

Provides one production Data-module call from authenticated CSV parsing to immutable raw storage, dedup, and canonical normalization. Implements the Data-owned transaction boundary defined in ARCH-04 and the raw-response-canonical-handoff contract.

## 2. Scope

### In Scope

- Data-owned `ingest_csv_upload()` service in `sawakli/data/ingestion/service.py`
- Single org-scoped transaction: persist `raw_api_responses` → staging → normalize/upsert → update `data_sources` freshness
- API route (`connectors.py`) calls the Data service instead of duplicating logic
- Unit tests for the ingestion service
- Task documentation

### Out of Scope

- OAuth connector ingestion (CONN-01 follow-up)
- Worker retry orchestration (WORK-03)
- UI CSV upload flow (UI-03)
- Real-time provider ingestion beyond CSV demo

## 3. Prerequisites

- **ARCH-04** — Connector-to-Data Handoff Contracts (accepted)
- **DATA-05** — Canonical Daily Metrics normalization (implemented)
- **raw-response-canonical-handoff** contract (accepted 2026-10-08)
- PostgreSQL migrations 0001–0003 applied
- CSV parser (`sawakli/connectors/csv/parser.py`) functional

## 4. Architecture

Per ARCH-04 and the canonical contract, the ingestion flow is:

```
Provider bytes (CSV file)
    ↓
ING-01 Connector parser (parse_csv_upload)
    ↓
API-03 authenticated source context
    ↓
Data-owned ingest_csv_upload() transaction
    ├─ Persist raw_api_responses (immutable evidence)
    ├─ Convert to StagedCampaignRow
    ├─ Normalize and upsert canonical entities
    └─ Update data_sources sync_status / last_synced_at
    ↓
Backend and AI canonical consumers
```

**Ownership Rule (ARCH-04):**
- Connector does NOT write Data tables
- API does NOT normalize rows
- Worker does NOT invent a second persistence path
- Data owns the transaction and freshness

## 5. Inputs

| Input | Type | Source | Notes |
|-------|------|--------|-------|
| `db` | `Session` | API dependency | SQLAlchemy session, caller manages transaction lifecycle |
| `raw_response` | `RawResponse` | Connector parser | Parsed CSV rows + warnings |
| `organization_id` | `UUID` | Auth token | Organization scope for tenant isolation |
| `data_source_id` | `UUID` | API route | Data source that owns this upload |
| `upload_id` | `UUID` | API route | Unique identifier for this raw response |
| `endpoint` | `str` | API route | CSV file identifier (e.g., `csv://upload/filename.csv`) |
| `raw_payload` | `dict[str, Any]` | API route | Raw CSV content for immutable storage |
| `synced_at` | `datetime` | API route | Timestamp for freshness tracking |

## 6. Outputs

| Output | Type | Description |
|--------|------|-------------|
| `IngestResult` | `dataclass` | Contains `row_count` and `parse_warnings` |

The service does NOT return canonical data — it commits to the database within the transaction. The API layer uses `IngestResult` to form the HTTP response.

## 7. Rules and Semantics

### Idempotency

The raw response insert uses `ON CONFLICT (id) DO NOTHING`, making duplicate upload_id calls safe. The dedup key for `raw_api_responses` is `(data_source_id, endpoint, fetched_at)` per the contract.

### Transaction Boundary

All four steps run in a single SQLAlchemy transaction:
1. Insert `raw_api_responses`
2. Stage parsed rows
3. Normalize and upsert canonical entities
4. Update `data_sources` freshness

The caller (API route) owns `db.commit()` / `db.rollback()`.

### Organization Isolation

Every operation includes explicit `organization_id` scoping. The normalization layer sets RLS context via `_set_org()`. Cross-tenant data exposure is a critical bug.

### Failure Handling

Per the contract:
- Empty file → `ConnectorError(retryable=false)` (caught by API before calling ingest)
- Malformed row → `RawResponse` with warnings (partial success)
- Database constraint failure → full rollback (handled by API exception handler)

## 8. Public Interfaces

### Module: `sawakli.data.ingestion`

```python
def ingest_csv_upload(
    db: Session,
    raw_response: RawResponse,
    organization_id: UUID,
    data_source_id: UUID,
    upload_id: UUID,
    endpoint: str,
    raw_payload: dict[str, Any],
    synced_at: datetime,
) -> IngestResult:
    """Persist a parsed CSV upload as an org-scoped, atomic ingest transaction."""

@dataclass(frozen=True)
class IngestResult:
    row_count: int
    parse_warnings: list[str]
```

### Caller: `sawakli.api.routes.connectors.upload_csv`

After parsing the CSV and validating the data source, the route calls:

```python
ingest_result = ingest_csv_upload(
    db=db,
    raw_response=result,
    organization_id=auth.organization.id,
    data_source_id=data_source_id,
    upload_id=upload_id,
    endpoint=f"csv://upload/{file.filename or 'upload.csv'}",
    raw_payload={"csv": content.decode("utf-8")},
    synced_at=synced_at,
)
db.commit()
```

## 9. Data Ownership

### Reads

- `data_sources` — verifies source exists and belongs to org (API layer)

### Writes

- `raw_api_responses` — immutable raw evidence (Data-owned)
- `campaigns`, `daily_metrics`, `ga_events` — canonical facts (Data-owned via normalization layer)
- `data_sources.sync_status`, `last_synced_at`, `last_error` — freshness (Data-owned)

### Must Never Read

- `connector_tokens` — Connector-owned, not used by Data layer
- User authentication tables — API layer concern

### Must Never Write

- Direct provider API calls — Connector responsibility
- User-facing error responses — API responsibility
- Feature tables — AI layer responsibility

## 10. Security

- Organization isolation is enforced at every query and mutation
- RLS context (`app.current_org_id`) is set by the normalization layer
- No secrets or credentials are handled by the Data layer
- Raw payload storage does not execute untrusted code (stored as JSONB, not evaluated)

## 11. Error and Edge-Case Behavior

| Scenario | Behavior |
|----------|----------|
| Empty parsed_rows | API catches before calling ingest, returns 422 |
| Database timeout | API catches exception, rolls back, marks data_sources as failed |
| Duplicate upload_id | INSERT ... ON CONFLICT DO NOTHING — idempotent |
| Cross-org data_source_id | API checks ownership before calling ingest, returns 404 |
| Partial row failure | Normalization layer skips invalid rows; transaction continues |

## 12. Testing

### Unit Tests

Location: `apps/backend/tests/unit/data/ingestion/test_service.py`

Coverage:
- `test_ingest_csv_upload_persists_raw_response` — verifies raw_api_responses insert
- `test_ingest_csv_upload_updates_data_sources_freshness` — verifies sync status update
- `test_ingest_csv_upload_handles_multiple_rows` — verifies batch processing
- `test_ingest_csv_upload_propagates_parse_warnings` — verifies warning passthrough
- `test_ingest_result_is_frozen` — verifies immutability

Run: `pytest tests/unit/data/ingestion/test_service.py`

### Integration Tests

QA-02 E2E test (`tests/integration/data/test_connector_to_canonical_e2e.py`) verifies the full CSV-to-canonical path including the Data-owned ingestion handoff.

### E2E Tests

Requires PostgreSQL test database. Verifies reconciliation:
- 2 campaigns, 3 daily_metrics rows, 3 ga_events rows
- Totals: spend=225, impressions=2250, clicks=225, conversions=23, revenue=450
- GA totals: sessions=1200, bounces=240
- Idempotency: second import produces same campaign_ids

## 13. Verification

### Type Checking

```bash
cd apps/backend
python -m mypy src/sawakli/data/ingestion/service.py src/sawakli/api/routes/connectors.py
```

**Result:** PASS — Success: no issues found in 2 source files

### Linting

```bash
cd apps/backend
ruff check src/sawakli/data/ingestion/ src/sawakli/api/routes/connectors.py
ruff format --check src/sawakli/data/ingestion/ src/sawakli/api/routes/connectors.py
```

**Result:** PASS — All checks passed! 3 files already formatted

### Unit Tests

```bash
cd apps/backend
python -m pytest tests/unit/data/ingestion/test_service.py -v
```

**Result:** PASS — 5 passed in 0.10s

### Integration Tests (QA-02)

```bash
cd apps/backend
python -m pytest tests/integration/data/test_connector_to_canonical_e2e.py -v
```

**Result:** PASS — 1 passed in 0.77s

## 14. Known Limitations

1. **Production Ingestion Job:** The service is wired into the API route but not yet invoked by a background Worker job (WORK-03 follow-up).

2. **Raw Response Dedup:** The migration does not have a unique constraint on `(data_source_id, endpoint, fetched_at)`. Idempotency relies on `ON CONFLICT (id) DO NOTHING` for upload_id, not on the full dedup key.

3. **Error Granularity:** The service returns a single `IngestResult`. Partial failures at the row level are communicated via `parse_warnings`, but there is no row-level error taxonomy beyond what the CSV parser provides.

4. **No Streaming:** The full CSV content is loaded into memory. Large files (>100 MB) may require a streaming approach in a future iteration.

## 15. Follow-Up Tasks

1. **WORK-03** — Wire the Data-owned ingest service into the Worker retry policy for scheduled and retried CSV imports.

2. **CONN-01** — Extend the ingest service to support OAuth providers (Meta, Google) with credential handling.

3. **API-03** — Extract CSV upload route orchestration into a dedicated service layer if additional providers are added.

4. **Performance Benchmarking** — Measure ingestion latency for 10k-row CSV files to validate production readiness.

5. **Raw Response Cleanup Policy** — Define retention policy for `raw_api_responses` (currently unbounded growth).

## 16. References and Evidence

- **Contract:** [docs/contracts/raw-response-canonical-handoff.md](../contracts/raw-response-canonical-handoff.md)
- **Architecture:** [docs/architecture/ARCH-04-connector-to-data-handoff-contracts.md](../architecture/ARCH-04-connector-to-data-handoff-contracts.md)
- **E2E Test:** [docs/testing/QA-02-connector-to-canonical-e2e.md](../testing/QA-02-connector-to-canonical-e2e.md)
- **Normalization:** [docs/data/DATA-05-canonical-daily-metrics.md](DATA-05-canonical-daily-metrics.md)

**Implementation Evidence:**
- Commit: (pending merge)
- Files added: `src/sawakli/data/ingestion/service.py`, `tests/unit/data/ingestion/test_service.py`
- Files modified: `src/sawakli/api/routes/connectors.py`
