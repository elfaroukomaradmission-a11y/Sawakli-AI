# API-03 — Safe Connector API Endpoints

## 1. Overview

API-03 exposes the Backend API endpoints needed to connect the UI/backend workflow to the Connector Layer safely.

It provides four HTTP interfaces:

1. Connector setup
2. CSV upload
3. OAuth authorization-code callback handoff
4. Connection-status lookup

The task exists to keep authentication, organization isolation, HTTP validation, and response shaping in the Backend while keeping provider token handling inside the Connector Layer.

In Sawakli AI, API-03 sits between the authenticated client/backend workflow and the Connector Layer.

## 2. Scope

### In Scope

- Protected connector setup endpoint.
- Organization-owned CSV/demo connector creation.
- Protected CSV upload endpoint.
- Organization ownership checks for connector resources.
- Safe translation of `ConnectorError` into HTTP responses using `user_message`.
- OAuth authorization-code callback handoff to `store_oauth_token()`.
- Safe connection-status endpoint using `check_connection_status()`.
- Dependency injection for the Connector `TokenExchanger` boundary.
- Focused API tests for authentication, organization isolation, OAuth handoff, status, and token non-exposure.

### Out of Scope

- Real Google Ads / Meta Ads OAuth HTTP client implementation.
- Provider-specific OAuth token exchange implementation.
- OAuth refresh orchestration.
- Background-worker scheduling.
- Data ingestion/normalization.
- AI analysis or anomaly detection.

The real provider `TokenExchanger` implementation belongs to the Connector layer and was not supplied by CONN-02.

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| API-01 | Provides JWT authentication, `get_auth_context()`, and organization isolation. |
| CONN-01 | Provides `parse_csv_upload()`, `RawResponse`, and `ConnectorError` for CSV handling. |
| CONN-02 | Provides OAuth token storage, connection-status logic, encryption, and the `TokenExchanger` / `TokenRepository` contracts. |
| DATA-01 / canonical database schema | Provides `data_sources`, `connector_tokens`, and related PostgreSQL schema used by the API and Connector layers. |

Relevant canonical contracts: API-01 authentication/organization boundary, CONN-01 CSV parser contract, CONN-02 OAuth/security contract, and the INT-01 canonical ownership/data contract.

## 4. Architecture

API-03 is the HTTP boundary between authenticated clients and the Connector Layer.

```text
Authenticated UI / Backend caller
              ↓
       API-03 FastAPI route
              ↓
    Authentication + org check
              ↓
       Connector boundary
        ↙             ↘
   CSV parser       OAuth services
                       ↓
               Encrypted token store
                       ↓
                  PostgreSQL
```

Ownership boundaries:

- Backend owns HTTP endpoints and organization authorization.
- Connector owns provider parsing and OAuth token handling.
- `connector_tokens` is Connector-owned exclusively.
- The API never returns access or refresh tokens.
- `data_source_id` is the ownership key for Connector token storage.
- SQL queries used by API-03 explicitly scope organization-owned `data_sources` by `organization_id`.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---:|---|---|
| Bearer token | HTTP `Authorization` header | Yes for protected routes | API-01 | Resolves authenticated user and organization through `get_auth_context()`. |
| `data_source_id` | UUID | Yes for CSV, OAuth callback, status | URL path | Identifies the connector resource. Server verifies organization ownership. |
| CSV file | multipart upload | Yes for CSV endpoint | Client | Passed to `parse_csv_upload()` without database/network handling in the parser. |
| `provider` | `Provider` enum | Yes for OAuth callback | JSON body | Must match the provider stored on the organization-owned `data_sources` row. |
| `code` | string | Yes for OAuth callback | JSON body | OAuth authorization code. Passed to Connector; never returned in the response. |
| `last_synced_at` | `datetime \| None` | No | `data_sources` read | Passed to `check_connection_status()` as the last successful sync timestamp. |

Validation and scope:

- Protected endpoints require API-01 authentication.
- `data_source_id` must belong to the authenticated organization.
- OAuth provider must match the stored connector provider.
- CSV uploads are accepted only for `csv_demo` sources.
- `last_synced_at` may be `NULL`.
- OAuth access and refresh tokens are not API inputs; they are produced and stored inside Connector.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---:|---|---|
| `data_source_id` | UUID | No | UI / Backend | Connector identifier. |
| `provider` | string / `Provider` | No | UI / Backend | Connector provider. |
| `status` | string | No | UI / Backend | Setup or OAuth connection status. |
| `row_count` | integer | No | UI / Backend | Number of accepted CSV rows. |
| `parsed_rows` | list of objects | No | UI / Backend | Parsed CSV data returned by CONN-01. |
| `parse_warnings` | list of strings | No | UI / Backend | Non-fatal parser warnings. |
| `connected` | boolean | No | UI / Backend | Whether a stored connector token exists. |
| `token_valid` | boolean | No | UI / Backend | Whether the stored token is currently valid according to CONN-02. |
| `last_successful_call_at` | datetime \| None | Yes | UI / Backend | `data_sources.last_synced_at` propagated through the Connector status contract. |
| Error `code` | string | Only on errors | UI / Backend | Safe typed error kind. |
| Error `message` | string | Only on errors | UI / Backend | Connector `user_message`; internal `ConnectorError.message` is not exposed. |
| Error `retryable` | boolean | Only on errors | UI / Backend | Whether retry is appropriate. |

Token values, encryption keys, authorization codes, and other Connector secrets are never included in successful API responses.

## 7. Rules and Semantics

### Connector setup

`POST /api/connectors/setup` creates an organization-owned `data_sources` row with:

- provider = `csv_demo`
- status = `disconnected`

The generated `data_source_id` identifies the connector.

### CSV upload

`POST /api/connectors/{data_source_id}/upload`:

- verifies organization ownership;
- verifies provider is `csv_demo`;
- creates an upload UUID;
- calls `parse_csv_upload(file.file, organization_id, upload_id)`;
- returns parsed rows and warnings on success;
- exposes only `ConnectorError.user_message` on parser failure;
- updates the source status to `demo_data` after a successful parse.

Malformed/unusable CSV behavior is inherited from CONN-01.

### OAuth callback

`POST /api/connectors/{data_source_id}/oauth/callback`:

- authenticates the caller;
- verifies connector ownership;
- verifies provider matches the stored source;
- passes only the authorization code to `store_oauth_token()`;
- does not return access or refresh tokens.

`store_oauth_token()` performs the Connector-side exchange and storage. The real CONN-02 contract returns `True` or `ConnectorError`.

### Connection status

`GET /api/connectors/{data_source_id}/status`:

- authenticates the caller;
- verifies connector ownership;
- reads `last_synced_at` from `data_sources`;
- constructs the Connector `PostgresTokenRepository`;
- calls `check_connection_status()`.

A missing stored token produces:

- `connected = false`
- `token_valid = false`

An expired token can produce:

- `connected = true`
- `token_valid = false`

A token with no known expiry is treated by CONN-02 as valid because no expiry evidence exists.

### Organization isolation

Every organization-owned connector lookup includes:

```sql
WHERE id = :data_source_id
  AND organization_id = :organization_id
```

Cross-organization access returns HTTP 404 instead of exposing whether another organization's connector exists.

## 8. Public Interfaces

### `POST /api/connectors/setup`

**Input:** authenticated request with no body.

**Output:** `data_source_id`, `provider`, `status`.

**Side effect:** inserts an organization-owned `data_sources` row.

### `POST /api/connectors/csv/{data_source_id}/upload`

**Input:** authenticated request plus multipart CSV file.

**Output:** parsed rows, row count, and parser warnings.

**Errors:** 404 for inaccessible/missing connector, 400 for non-CSV connector, 422 for unusable CSV.

**Side effect:** marks the CSV/demo source as `demo_data` after successful parsing.

### `POST /api/connectors/{data_source_id}/oauth/callback`

**Input:** authenticated request containing `provider` and OAuth authorization `code`.

**Output:** `data_source_id`, `provider`, and safe connection status.

**Errors:** 404 for inaccessible connector, 400 for provider mismatch or non-retryable Connector errors, 502 for retryable provider errors, 503 when connector security/provider configuration is unavailable.

**Side effect:** delegates token exchange and secure storage to Connector.

### `GET /api/connectors/{data_source_id}/status`

**Input:** authenticated request and `data_source_id`.

**Output:** `connected`, `token_valid`, `last_successful_call_at`.

**Errors:** 404 for inaccessible/missing connector, 503 if Connector security configuration is unavailable.

## 9. Data Ownership

### Reads

- `data_sources.id`
- `data_sources.provider`
- `data_sources.last_synced_at`

API-03 also invokes Connector status logic, which reads `connector_tokens` through `PostgresTokenRepository`.

### Writes

- Creates `data_sources` rows for connector setup.
- Updates `data_sources.status` for successful CSV/demo uploads.

Connector token writes are performed by `PostgresTokenRepository`, not directly by API business logic.

### Must Never Read

- Raw OAuth access tokens outside the Connector boundary.
- Raw OAuth refresh tokens outside the Connector boundary.
- Encryption keys for any purpose other than passing them to the Connector repository boundary.

### Must Never Write

- Plaintext OAuth tokens to UI responses.
- OAuth tokens or authorization codes to logs.
- Token values into `data_sources`.
- Token values into `oauth_connections`.

## 10. Security

API-03 uses API-01's `get_auth_context()` dependency for protected routes.

Security controls implemented:

- JWT authentication on all connector endpoints.
- Explicit organization ownership checks.
- Cross-organization connector access returns 404.
- OAuth provider mismatch is rejected.
- OAuth authorization code is passed only to Connector.
- Access and refresh tokens are never returned by API-03.
- Connector errors expose `user_message`, not internal `message`.
- Token storage uses the CONN-02 `PostgresTokenRepository`.
- CONN-02 encrypts token values with AES-256-GCM before persistence.
- `connector_tokens` is Connector-owned exclusively.

The encryption key is loaded from `CONNECTOR_TOKEN_ENCRYPTION_KEY` and is not part of any API response.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Missing input | FastAPI validation rejects the request. |
| Malformed CSV | CONN-01 returns a typed `ConnectorError`; API exposes safe `user_message`. |
| Invalid/missing connector | HTTP 404. |
| Cross-organization connector | HTTP 404. |
| CSV sent to non-CSV connector | HTTP 400. |
| OAuth provider mismatch | HTTP 400. |
| Invalid OAuth authorization code | Safe non-retryable Connector error; no code/token exposure. |
| Provider unavailable | Safe retryable error; HTTP 502 from the callback route. |
| Missing encryption configuration | HTTP 503; no secret material is exposed. |
| No stored token | Status returns `connected=false`, `token_valid=false`. |
| Expired token | Status can return `connected=true`, `token_valid=false`; no exception is required. |
| Token with null expiry | CONN-02 treats the token as valid because there is no known expiry. |
| Duplicate token record | The repository uses `data_source_id` uniqueness and upsert behavior. |
| Database failure | Normal database exception propagation; no sensitive values should be included in route responses. |
| Timeout | Provider/network retryability is represented through Connector error semantics. |
| Cancellation | N/A — no API-03-specific cancellation workflow is implemented. |

## 12. Testing

### Unit Tests

CONN-02 already provides unit coverage for:

- token exchange success/failure;
- refresh behavior;
- expired/missing tokens;
- encryption repository behavior.

API-03 relies on those Connector contracts rather than duplicating token business logic.

### Integration Tests

API-03 focused tests cover:

- setup authentication;
- setup creation;
- successful CSV parsing;
- parser warnings;
- invalid CSV handling;
- cross-organization CSV protection;
- connection-status authentication;
- connection status with no stored token;
- cross-organization status protection;
- OAuth callback authentication;
- cross-organization OAuth protection;
- OAuth provider mismatch;
- authorization-code handoff;
- token non-exposure in HTTP responses.

Focused API test result:

```text
13 passed
```

The CONN-02 PostgreSQL repository also has dedicated integration tests in the existing Connector test suite.

### E2E Impact

API-03 provides the backend endpoints required for a future UI connector workflow.

A real production OAuth flow still requires a concrete provider `TokenExchanger` implementation.

## 13. Verification

Commands executed:

```bash
ruff check src/sawakli/api/routes/connectors.py src/sawakli/api/main.py tests/test_connectors_api.py tests/conftest.py
ruff format --check src/sawakli/api/routes/connectors.py src/sawakli/api/main.py tests/test_connectors_api.py tests/conftest.py
mypy src
py -3.12 -m pytest tests/test_connectors_api.py -v
```

Results on 2026-09-15:

- `ruff check ...` — PASS
- `ruff format --check ...` — PASS
- `mypy src` — PASS: `Success: no issues found in 88 source files`
- focused connector API tests — PASS: `13 passed`

The mypy command emitted configuration warnings about the `jose` and `passlib` per-module sections, but reported no type-checking errors.

A full suite was also executed:

```bash
py -3.12 -m pytest
```

Result:

```text
247 passed, 9 skipped, 2 failed
```

The two failures were unrelated AI integration tests:

- `tests/integration/ai/test_database_loader.py::test_seeded_nour_database_loads_all_campaign_days_in_order`
- `tests/integration/ai/test_forecasting_integration.py::test_seeded_nour_data_generates_read_only_forecasts_and_evaluations`

Both failed because the expected seeded Nour metrics were unavailable (`0` loaded rows), causing the downstream forecast assertion to fail.

CI / pull-request evidence: N/A — no API-03 pull request was created at the time of this documentation.

## 14. Known Limitations

- CONN-02 defines the `TokenExchanger` interface but does not provide a concrete provider HTTP implementation. API-03 therefore exposes and tests the handoff boundary through dependency injection.
- The real provider OAuth exchange remains dependent on a future Connector implementation.
- The full repository test suite is not completely green because of the two unrelated AI seeded-data integration failures described above.
- Existing third-party deprecation warnings remain in the test output.

## 15. Follow-Up Tasks

- Connector provider OAuth implementation — Connector layer owner — provide a concrete `TokenExchanger` for the required providers.
- Resolve the unrelated Nour seeded-data integration failures — AI/Data owners — restore the expected full-suite integration coverage.
- Create and review the API-03 pull request — Backend owner — merge the completed API-03 branch into `main`.

## 16. References and Evidence

- Notion task: API-03 — Expose safe backend endpoints for connector setup, CSV upload, OAuth callback handoff and connection status.
- Pull request: N/A — API-03 branch is ready, but no pull request was created at documentation time.
- CONN-01 PR: https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/1
- CONN-02 PR: https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/4
- Repository: https://github.com/elfaroukomaradmission-a11y/Sawakli-AI
- Canonical contracts: API-01, CONN-01, CONN-02, INT-01.
- Test evidence: `tests/test_connectors_api.py` — 13 passing API tests.
- Verification evidence: Ruff, Ruff format, mypy, and pytest outputs recorded on 2026-09-15.
