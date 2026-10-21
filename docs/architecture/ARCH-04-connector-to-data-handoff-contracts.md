# ARCH-04 — Resolve Connector-to-Data Handoff Contracts

## 1. Overview

ARCH-04 defines the Data-owned handoff from a Connector `RawResponse` to immutable raw evidence and
organization-scoped canonical facts. It resolves persistence, normalization, deduplication,
freshness, error, retry, and credential boundaries for ING-01, API-03, and WORK-03.

The shared contract is canonical in
[`raw-response-canonical-handoff.md`](../contracts/raw-response-canonical-handoff.md).

## 2. Scope

### In Scope

- Persisting provider-faithful raw payloads as immutable evidence
- Staging and normalizing only rows accepted by the Connector
- Canonical upsert keys for campaigns, daily metrics, and GA events
- Source freshness and failure status ownership
- Safe failure classification and bounded retry handoff
- Organization isolation and credential redaction rules

### Out of Scope

- Provider-specific parsing or OAuth exchange (ING-01 / Connector)
- Authentication, organization resolution, or HTTP response translation (API-03 / API)
- Worker scheduling policy beyond invoking the published ingest contract (WORK-03 / Worker)
- New database tables or migrations

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| TRK-04 baseline | W2 entry contract and authoritative prerequisite |
| ING-01 | Supplies `RawResponse` and typed connector failures |
| API-03 | Supplies authenticated organization and owned data-source context |
| WORK-03 | Invokes the handoff and applies retry policy |
| [RawResponse and Canonical Handoff Contract](../contracts/raw-response-canonical-handoff.md) | Shared ownership and error semantics |
| DATA-05 | Supplies canonical metric and GA event normalization |
| QA-02 | Provides the deterministic malformed-row and duplicate-row fixture |

## 4. Architecture

```text
Provider bytes
    ↓
ING-01 Connector parser
    ↓ RawResponse / ConnectorError
API-03 authenticated source context
    ↓
WORK-03 invokes Data-owned transaction
    ↓
raw_api_responses → staging → normalization/upsert
    ↓
data_sources freshness/status → Backend and AI canonical consumers
```

The Connector does not write Data tables. The API does not normalize provider rows. The Worker does
not invent a second persistence path. Data owns the transaction and canonical handoff.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `RawResponse` | dataclass | Yes for accepted pull | ING-01 | Valid rows, row count, and parse warnings |
| `ConnectorError` | dataclass | Yes for failed pull | ING-01 | Typed failure and retryability |
| `data_source_id` | UUID | Yes | API-03 auth context | Must belong to authenticated organization |
| provider payload | JSONB | Yes for raw evidence | Connector pull | Provider-faithful; credentials excluded |

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `raw_api_responses` row | PostgreSQL row | No | Audit/Data | Immutable pull evidence |
| canonical campaigns | PostgreSQL rows | No | Backend/AI | Deduplicated campaign identity |
| canonical daily metrics | PostgreSQL rows | No | Backend/AI | Deduplicated `(campaign_id, date)` facts |
| canonical GA events | PostgreSQL rows | No | Backend/AI | Deduplicated `(campaign_id, date)` aggregates |
| source freshness/status | `data_sources` columns | `last_synced_at` yes | API/UI/Worker | Updated only after successful canonical commit |

## 7. Rules and Semantics

- Raw evidence is retained per accepted pull; canonical facts are idempotent on their database
  keys. Replaying the same source, endpoint, and `fetched_at` uses the raw-response idempotency
  key; a new fetch timestamp is a new evidence record.
- Parse warnings exclude invalid rows without turning a partial parse into a fabricated success.
- Empty/file-level parse failures create no canonical facts and do not advance freshness.
- A transaction failure rolls back the attempted raw and canonical writes.
- Retryability is explicit: provider availability and transient database errors may retry; invalid
  input and rejected credentials require correction or reconnect.
- Freshness is Data-owned and means successful canonical persistence, not merely a provider call.

## 8. Public Interfaces

- `parse_csv_upload(...)` returns `RawResponse | ConnectorError`; it performs no I/O.
- `normalize_and_upsert_batch(...)` receives staged rows and upserts organization-scoped canonical
  facts.
- The production ingest call must preserve the transaction and error semantics in the canonical
  contract. API and Worker must not bypass it.

## 9. Data Ownership

### Reads

- Authenticated organization/source context supplied by API-03
- Connector output supplied by ING-01
- Existing organization-scoped canonical rows for upsert conflict resolution

### Writes

- `raw_api_responses`
- staging and canonical Data-owned facts
- `data_sources.sync_status`, `last_synced_at`, and `last_error`

### Must Never Read

- Another organization's payloads or canonical facts
- Decrypted credentials, authorization codes, or provider tokens

### Must Never Write

- Credentials into raw payloads, logs, errors, or API responses
- Canonical facts without organization/source scope
- AI-owned tables or a duplicate ingestion cache

## 10. Security

The authenticated organization is the trust boundary. `data_source_id` is checked against it before
the handoff. Connector token storage remains Connector-owned and encrypted; Data receives provider
data, not token material.

## 11. Error and Edge-Case Behavior

See the failure/retry matrix in the
[canonical contract](../contracts/raw-response-canonical-handoff.md). In particular, retries run
the whole handoff and never report partial canonical writes as success.

## 12. Testing

### Unit Tests

- Connector tests cover `RawResponse`, typed file failures, row warnings, and retryability.
- Data tests cover campaign and campaign-day idempotent upserts.

### Integration Tests

- QA-02 proves four valid rows, one malformed row, one repeated valid row, raw evidence, exact
  reconciliation, and stable IDs after replay.
- API connector tests prove invalid files fail safely and successful uploads update freshness.

### E2E Impact

No live provider call is required. A replayable GA4 fixture remains a separate follow-up.

## 13. Verification

Commands executed:

```powershell
cd "D:/projects/Sawakli-AI/apps/backend"; & "C:/Users/cairo/AppData/Local/Programs/Python/Python314/python.exe" -m pytest tests/integration/data/test_connector_to_canonical_e2e.py -q
```

Result:

- `PASS` — existing QA-02 evidence records `1 passed`.
- New documentation and contract changes require the repository governance check to be run before
  review.

## 14. Known Limitations

- The current production CSV route still contains orchestration code; extraction into the
  Data-owned ingest call is a WORK-03 implementation follow-up.
- Raw persistence for file-level parse failures is intentionally not required by this bounded
  decision; the safe failure is recorded on `data_sources`.
- No live provider or credential-refresh integration is exercised.

## 15. Follow-Up Tasks

- ING-01: keep provider adapters limited to parsing and safe typed errors.
- API-03: pass only authenticated source context and the canonical error envelope.
- WORK-03: expose the Data-owned transactional ingest call and apply bounded retries.

## 16. References and Evidence

- [RawResponse and Canonical Handoff Contract](../contracts/raw-response-canonical-handoff.md)
- [QA-02 connector-to-canonical E2E](../testing/QA-02-connector-to-canonical-e2e.md)
- `tests/contracts/canonical.json` — added `data_sources` ownership/freshness and
  `raw_api_responses` immutability/credential semantics
- Required reviewer: `@elfaroukomaradmission-a11y` per `.github/CODEOWNERS`
