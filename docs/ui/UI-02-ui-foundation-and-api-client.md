# UI-02 — Frontend Foundation and API Client

## 1. Overview

UI-02 supplies the active Next.js shell, protected routes, navigation, browser session handling,
and a typed UI-to-API boundary.

## 2. Scope

### In Scope

- App/auth route structure, sidebar, top bar, and route guard.
- Typed API client, error translation, and same-origin FastAPI proxy.
- UI-01 design-token reuse and focused frontend tests.

### Out of Scope

- API authentication, JWT creation, organization authorization, CORS policy, or persistence.
- Dashboard/business APIs, CSV ingestion, OAuth, AI output, export, and UI-04–UI-09 features.

## 3. Prerequisites

| Task / contract | Why required |
|---|---|
| UI-01 | Provides the existing visual tokens and layout patterns. |
| DEV-01 | Provides the Next.js application and Compose API URLs. |
| API-01 | Defines the auth routes and authenticated organization boundary. |

No ADR or canonical frontend API contract exists in `docs/contracts` at this commit.

## 4. Architecture

```text
Browser page → /api/* Next.js proxy → FastAPI /api/* → Backend contract
```

The proxy uses `API_INTERNAL_URL`, then `NEXT_PUBLIC_API_URL`, then the local development default.
It forwards method, content type, and bearer token only; it does not inspect or persist tokens.

## 5. Inputs

| Input | Type | Required | Source | Meaning |
|---|---|---:|---|---|
| API path | string | Yes | UI service | Same-origin path such as `/api/auth/login`. |
| bearer token | string | Protected requests | API-01 login | Forwarded as `Authorization`. |
| backend error detail | string/object | No | FastAPI | Converted to a safe `ApiError`. |

## 6. Outputs

| Output | Type | Consumer | Meaning |
|---|---|---|---|
| parsed API result | generic `T` | UI services/pages | Contract-shaped successful response. |
| `ApiError` | error | UI pages | Safe message plus status/code/retryability. |
| session | browser storage | protected UI | User, organization, and bearer token from API-01. |

## 7. Rules and Semantics

- A 401 produces a sign-in-again message; API authorization remains authoritative.
- The middleware cookie is a route hint only, not server authorization.
- Failed/unavailable API calls never become mock successful responses.
- The proxy avoids a browser CORS dependency; API CORS remains owned by Backend deployment.

## 8. Public Interfaces

- `apiRequest<T>(path, options)` — calls the same-origin proxy and returns typed JSON or `ApiError`.
- `POST /api/*` and `GET /api/*` Next.js route handler — forwards approved API requests to FastAPI.

## 9. Data Ownership

### Reads

- Auth and connector API responses.
- Existing browser session only for user, organization, and bearer token.

### Writes

- Existing browser session storage and route-hint cookie.

### Must Never Read

- Database, provider credentials, encryption keys, or connector tokens.

### Must Never Write

- Organization-owned records or provider tokens.

## 10. Security

The browser sends the API-01 bearer token only to the same-origin proxy. The API derives
organization scope from that token. No organization ID is sent by UI. The current browser-storage
session is documented as a limitation; a future approved API/session contract may use HTTP-only
cookies.

## 11. Error and Edge-Case Behavior

| Case | Behavior |
|---|---|
| 401 | Explain that the session expired; user signs in again. |
| 403/404 | Display safe generic permission/not-found message. |
| typed connector error | Preserve safe code/message/retryable fields. |
| proxy/API unavailable | Return safe retryable 503 response. |
| invalid session storage | Treat as no session. |

## 12. Testing

### Unit Tests

- `api-client.test.ts` proves token forwarding and safe error mapping.

### Integration Tests

- The proxy and real API need an API-01/API-03 deployment for HTTP integration verification.

### E2E Impact

- UI-03’s focused component test covers the CSV request choreography; browser E2E remains follow-up.

## 13. Verification

Executed 2026-10-01 from `apps/web` after merging PR #16:

- `node_modules/.bin/eslint.cmd .` — PASS; two pre-existing unused `_orgId` warnings in mock campaign/recommendation services.
- `node_modules/.bin/tsc.cmd --noEmit` — PASS.
- `node_modules/.bin/vitest.cmd run` — PASS; 3 files, 6 tests.
- `node_modules/.bin/next.cmd build` — PASS; Next.js reports the repository’s existing middleware-to-proxy deprecation warning.

## 14. Known Limitations

- API-01 returns one organization from `/api/auth/me`; no approved organization-list/switch contract exists.
- The API proxy is tested in frontend unit/build checks but not yet against a running local API stack.

## 15. Follow-Up Tasks

- ARCH-06 — UI owner — document and review the long-term API/session/state decision.
- API-07 — Backend owner — publish standardized error/OpenAPI contract.
- UI-08 — UI owner — consolidate product-wide loading, empty, error, and export states.

## 16. References and Evidence

- API-01 routes: `apps/backend/src/sawakli/api/routes/auth.py`.
- API client: `apps/web/src/lib/api-client.ts`.
- Proxy: `apps/web/src/app/api/[...path]/route.ts`.
- Tests: `apps/web/tests/api-client.test.ts`.
