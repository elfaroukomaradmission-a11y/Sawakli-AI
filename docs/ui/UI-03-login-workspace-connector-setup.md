# UI-03 — Login, Workspace, and CSV Connector Setup

## 1. Overview

UI-03 provides account/workspace creation, login, and a real CSV validation flow. A CSV result is
called **validated**, never processed or fresh, until Data-owned ING-01 is integrated.

## 2. Scope

### In Scope

- Create the first workspace through API-01 registration.
- Login, authenticated current-user lookup, CSV selection, upload, result/warning/error states.
- Honest unavailable OAuth and dashboard-demo states without secret exposure.

### Out of Scope

- Organization switching; no API-01 list/switch contract exists.
- Persistence, canonical normalization, idempotency, data processing, or freshness: ING-01/Data owns these.
- Provider OAuth flow: CONN-03/Connector owns it.
- Real dashboard values: API-02/UI-04 own them.

## 3. Prerequisites

| Task / contract | Why required |
|---|---|
| UI-02 | Supplies session, API client, proxy, and application shell. |
| API-01 | Supplies registration, login, current-user, and organization scope. |
| API-03 / PR #18 | Supplies connector setup and CSV parsing/upload routes. |
| ING-01 | Future source of persisted processing/readiness truth. |

## 4. Architecture

```text
Create workspace or sign in
↓
API-01 returns authenticated organization
↓
API-03 creates csv_demo source
↓
API-03 parses uploaded CSV
↓
UI displays validated row count/warnings
↓
ING-01 later makes processing/readiness available
```

## 5. Inputs

| Input | Type | Required | Source | Meaning |
|---|---|---:|---|---|
| name/email/password/workspace | strings | Yes for registration | user | API-01 registration fields. |
| CSV file | `File` | Yes for upload | user | `.csv` extension required by UI. |
| bearer token | string | Yes | API-01 login | scopes connector requests. |

## 6. Outputs

| Output | Type | Consumer | Meaning |
|---|---|---|---|
| browser session | user/org/token | UI shell | Authenticated workspace context. |
| CSV result | API-03 response | setup page | row count and safe parse warnings. |
| status message | UI state | user | loading, validation error, validated, or unavailable. |

## 7. Rules and Semantics

- Actual API-03 URL: `POST /api/connectors/csv/{data_source_id}/upload`, multipart field `file`.
- UI creates a `csv_demo` source with `POST /api/connectors/setup` before first upload.
- Only a successful parser response enables “Continue to demo dashboard.”
- Parsed rows are intentionally not rendered; they may be large and are not onboarding output.
- CSV validation does not equal persisted ingestion, canonical readiness, connected OAuth, or dashboard freshness.

## 8. Public Interfaces

- `createCsvConnector(accessToken)` — invokes API-03 setup.
- `uploadCsv(accessToken, dataSourceId, file)` — sends multipart CSV to API-03.
- `getConnectorStatus(...)` — typed API-03 status facade retained for a future truthful source-status contract; not called for CSV processing state today.

## 9. Data Ownership

### Reads

- API-01 user/organization responses and API-03 safe upload response.

### Writes

- UI writes only its browser session; API-03 writes the connector source.

### Must Never Read

- OAuth codes, access/refresh tokens, encryption keys, raw database data, or other organizations’ sources.

### Must Never Write

- Canonical metrics, raw payloads, data-source processing status, or provider credentials.

## 10. Security

The frontend never supplies an organization ID. API-01 scopes the bearer token and API-03 checks
data-source ownership. API error text is shown only from the safe contract. OAuth providers are
marked unavailable rather than presenting a fake login or asking for secrets.

## 11. Error and Edge-Case Behavior

| Case | Behavior |
|---|---|
| no file/non-CSV file | Block upload and explain the requirement. |
| upload in progress | Disable selection/upload controls and show progress wording. |
| API parser error | Show safe API message and allow retry. |
| unavailable API | Show safe retryable unavailable message. |
| parser warning | Show warning count and individual safe warnings. |
| successful parser result | Show validated row count, not processing/freshness claim. |
| no session | Return to login rather than send an unauthenticated request. |

## 12. Testing

### Unit Tests

- `connector-setup.test.tsx` verifies source creation, exact upload service call, validation result,
  no-processing message, and non-CSV rejection.

### Integration Tests

- API-03 route integration is owned by API-03. UI real HTTP verification requires PR #18 deployed.

### E2E Impact

- A full run must register/login, upload a valid fixture, assert row/warnings, and confirm the demo
  dashboard notice; it cannot assert canonical data until ING-01 exists.

## 13. Verification

Executed 2026-10-01 from `apps/web`:

- `pnpm run lint` — PASS; only two pre-existing mock-service warnings.
- `pnpm run type-check` — PASS.
- `pnpm test` — PASS; connector setup component assertions included in 6 passing tests.
- `pnpm run build` — PASS.

## 14. Known Limitations

- PR #18 must be merged/deployed before the live upload flow works.
- PR #18 parses CSV but does not invoke ING-01 persistence/normalization; UI deliberately reports processing/freshness unavailable.
- PR #18’s status route reports connector-token health and is not a CSV processing/freshness contract.
- Current dashboard cards remain clearly labeled interface demo data.

## 15. Follow-Up Tasks

- ING-01 — Data/Connector owner — persist uploads and expose readiness/processing state.
- API-03 — Backend owner — merge/deploy and reconcile its documented endpoint wording with route code.
- CONN-03 — Connector owner — provide a real OAuth authorization/provider implementation.
- API-02/UI-04 — Backend/UI owners — serve real organization-scoped dashboard data.

## 16. References and Evidence

- API-01: `apps/backend/src/sawakli/api/routes/auth.py`.
- PR #18 route source: `apps/backend/src/sawakli/api/routes/connectors.py` on `origin/pr-18`.
- UI service: `apps/web/src/services/connectors.service.ts`.
- UI test: `apps/web/tests/connector-setup.test.tsx`.
