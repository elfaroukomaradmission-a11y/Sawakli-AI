# RawResponse and Canonical Handoff Contract

**Status:** Accepted — 2026-10-08  
**Owner:** Data layer  
**Required reviewer:** `@elfaroukomaradmission-a11y` (CODEOWNERS); review must include the
ING-01, API-03, and WORK-03 owners before implementation changes are merged.

## Decision

The Connector layer parses provider bytes and returns a `RawResponse` or a typed
`ConnectorError`. It does not write PostgreSQL rows, normalize values, deduplicate facts, update
source freshness, or handle credentials.

The Data-owned ingest handoff performs these steps in one organization-scoped transaction:

1. Persist the provider-faithful payload as an immutable `raw_api_responses` row.
2. Convert accepted `RawResponse.parsed_rows` into Data staging rows.
3. Normalize and upsert canonical entities and campaign-day facts.
4. Update `data_sources` sync status and `last_synced_at` only after canonical writes commit.

The raw row is evidence of the provider pull, not a canonical fact. Replaying an identical raw
payload with the same source, endpoint, and fetch timestamp is idempotent; distinct pulls remain
evidence. Canonical rows are deduplicated by their database keys and upserted.

## Contract

### Connector output

`RawResponse` contains:

- `parsed_rows`: valid, cleaned rows only;
- `row_count`: `len(parsed_rows)`;
- `parse_warnings`: row-scoped warnings that do not enter staging.

`ConnectorError` contains `kind`, an internal `message`, a safe `user_message`, and `retryable`.
Provider credentials, access tokens, refresh tokens, and authorization codes never appear in
either output or logs.

### Persistence and deduplication

| Record | Owner | Persistence decision | Deduplication key |
|---|---|---|---|
| `raw_api_responses` | Data | Immutable provider-faithful JSON payload, persisted before normalization | `(data_source_id, endpoint, fetched_at)`; distinct pulls remain evidence |
| `campaigns` | Data | Normalize and upsert | `(data_source_id, external_id)` when present; CSV fallback `(data_source_id, name)` |
| `daily_metrics` | Data | Normalize and upsert | `(campaign_id, date)` |
| `ga_events` | Data | Normalize and upsert | `(campaign_id, date)` |

The organization is derived from the authenticated source ownership and is required on every
staging and canonical write. A client-supplied organization identifier is never trusted.

### Freshness ownership

Data owns `data_sources.sync_status`, `data_sources.last_synced_at`, and `data_sources.last_error`.
`last_synced_at` means the time of the most recent pull whose accepted rows were persisted
successfully into canonical tables. A parse failure or transaction rollback must not advance it.
Connector may read the value for connection-status reporting but must not write it.

## Failure and retry examples

| Example | Connector result | Persistence | Retry |
|---|---|---|---|
| Empty file or invalid header | `ConnectorError(retryable=false)` | No raw or canonical row; source marked `failed` with a safe message | User fixes the file; automatic retry is not scheduled |
| One malformed row among valid rows | `RawResponse` with valid rows and `parse_warnings` | Raw payload and valid canonical rows persist; malformed row is excluded | No automatic retry; warning is actionable |
| Provider timeout / unavailable API | `ConnectorError(retryable=true)` | No canonical write; source error is recorded without credentials | Worker may retry with bounded exponential backoff |
| Credential rejected or expired | `ConnectorError(retryable=false)` | No token or raw credential is persisted in the payload; source remains disconnected/failed | Reconnect is required; do not retry the same credential |
| Database or canonical constraint failure | Ingest transaction fails after parsing | Roll back raw and canonical writes from that attempt; retain the error and do not advance freshness | Worker retries the whole ingest only when the failure is classified transient |

Retrying must re-run the complete Data handoff, not only canonical upserts. Partial success must
never be reported as a successful sync.

## Affected implementation steps and review

| Step | Affected task | Owner boundary | Required review |
|---|---|---|---|
| Parse bytes, validate header/rows, emit `RawResponse`/`ConnectorError` | ING-01 | Connector | Connector parsing review |
| Authenticate organization, select owned `data_source`, expose safe API errors | API-03 | API | API ownership and error-shape review |
| Persist raw payload, stage/normalize/upsert, update freshness, retry transaction | WORK-03 | Data/Worker handoff | Data contract review plus Worker retry review |

`TRK-04` is the prerequisite baseline. The W2 ingest call is Data-owned; API and Worker invoke it
through its published contract rather than writing canonical tables independently.

## Security invariants

- Every read and write is scoped through an authenticated organization-owned `data_source_id`.
- Raw payloads may contain provider data but never credentials or authorization material.
- Error responses and logs use safe user messages and identifiers only; token values are never
  interpolated.
- Canonical consumers read normalized tables, never raw payloads as if they were facts.
