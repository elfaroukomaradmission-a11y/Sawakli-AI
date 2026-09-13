# UI-03 — Build Login, Workspace and Connector Setup UI

## 1. Overview

This task implements the first-use web entry flow for Sawakli AI. It gives a user a usable path from login or account creation into an organization workspace, then into demo data or CSV source setup.

The flow belongs to the Web layer and consumes the existing Backend authentication contract. It displays connection state and import metadata without rendering passwords, access tokens, OAuth codes, or provider secrets.

Status: **Implemented** for the web entry experience. CSV selection is currently a client-side setup state; server-side import persistence remains a follow-up because no CSV upload API contract exists in the current Backend surface.

## 2. Scope

### In Scope

- Login against the existing `/api/auth/login` endpoint
- Authenticated workspace hydration through `/api/auth/me`
- Account and first-workspace creation through `/api/auth/register`
- Explicit demo workspace entry
- CSV file selection with extension, filename, size, and ready-to-import state
- Safe connector status display for supported OAuth connector types
- Loading, error, unauthorized/request-failure, empty-source, and selected-source states
- Focused flow tests for source selection and safe status presentation

### Out of Scope

- Adding a new Backend workspace-list or organization-switch endpoint
- Persisting CSV bytes or normalized rows to the Backend
- Implementing OAuth redirects, provider token exchange, or token storage
- Displaying provider credentials or connection secrets in the browser
- Changing dashboard analytics or campaign data contracts

Workspace selection in this version means creating the authenticated user’s first organization through the approved registration path, or entering the existing organization returned by `/api/auth/me`. Multi-organization switching requires a Backend contract that is not present today.

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| API-01 authentication | Defines login, registration, bearer token, and authenticated user behavior |
| API-03 organization access | Defines organization identity returned by the authenticated `/me` endpoint |
| UI-02 application shell | Provides the Next.js route groups, styling tokens, and dashboard destination |
| `apps/backend/src/sawakli/api/schemas/auth.py` | Current source of truth for login, register, and `/me` response fields |
| `apps/backend/src/sawakli/api/routes/auth.py` | Current source of truth for authentication endpoint paths and error behavior |

## 4. Architecture

```text
Login or registration form
        |
        v
Typed Web auth service
        |
        v
FastAPI /api/auth contract
        |
        v
Session with user + organization identity
        |
        v
Source setup: demo selection or CSV selection
        |
        v
Dashboard workspace
```

Ownership boundaries:

- Web owns form state, navigation, safe status display, and browser-side session presentation.
- Backend owns authentication, password verification, organization creation, and authenticated organization scope.
- Connector/Data layers own provider authorization, token handling, CSV parsing, staging, normalization, and persistence.
- This task does not duplicate connector token handling or invent a second organization contract.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `email` | string | Yes | Login/register form | User email sent to the Backend auth contract |
| `password` | string | Yes | Login/register form | Password sent only in the HTTPS API request |
| `name` | string | Yes for registration | Registration form | User display name |
| `organization_name` | string | Yes for registration | Workspace setup form | Name of the first organization/workspace |
| `access_token` | string | Yes after login | Backend login response | Used in the Authorization header for `/me`; never rendered |
| `File` | browser `File` | Optional | CSV chooser | Client-side file selection; only filename, size, and readiness are displayed |
| demo choice | `'demo'` | Optional | Source setup action | Selects the prepared demo entry path |

Validation:

- Required form fields use native browser validation.
- Registration password requires at least eight characters in the UI.
- CSV selection accepts `.csv` / `text/csv` only.
- Continue is blocked until either demo data or a CSV is selected.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `AuthResponse` | typed object | No | Session setup | Backend login response containing user and access token |
| `RegisterResponse` | typed object | No | Session setup | Backend registration response containing user and organization |
| `MeResponse` | typed object | No | Session setup | Authenticated user and organization identity |
| session | browser session record | Yes before auth | Dashboard/setup routes | Stores user, organization, and access token for the current demo app shell |
| source state | `'demo' \| 'csv' \| null` | Yes | Connector setup screen | Controls safe source readiness and navigation |
| visible source status | text/badge | No | User | Shows `Available`, `Ready to import`, or selected demo state without secrets |

## 7. Rules and Semantics

- Login calls `/api/auth/login`, then `/api/auth/me`; the organization is taken from the authenticated `/me` response rather than from query parameters or user input.
- Registration calls `/api/auth/register`, then logs in with the submitted credentials to obtain the access token required by the current session model.
- The first-workspace path is the organization returned by registration. The current Backend contract does not expose a list/create-many workspace selector.
- Demo data is an explicit choice and does not claim a provider connection.
- CSV selection displays only safe local metadata: filename, size, and `Ready to import` status.
- OAuth connector rows display availability and connector type only. No token, authorization code, or credential input is rendered.
- The dashboard route is not opened when no source has been selected.
- Request failures are shown as user-safe messages from the Backend `detail` field or a generic fallback; raw response bodies are not rendered.
- Missing backend CSV persistence is not represented as a successful import. The current UI records selection readiness only.

## 8. Public Interfaces

### `login(email, password)`

Calls `POST /api/auth/login` and returns the typed `AuthResponse`. Non-2xx responses become an error for the login screen.

### `register(name, email, password, organizationName)`

Calls `POST /api/auth/register` with the backend field `organization_name` and returns the typed `RegisterResponse`.

### `readMe(accessToken)`

Calls `GET /api/auth/me` with a bearer Authorization header and returns the authenticated user and organization. The token is not rendered in the UI.

### Entry routes

- `/login` — existing account login or explicit demo entry
- `/setup/organization` — account and first-workspace creation
- `/setup/connector` — demo/CSV source selection and safe status display
- `/dashboard` — destination after a valid session and source choice

## 9. Data Ownership

### Reads

- Reads the Backend authentication responses through the typed Web auth service.
- Reads local browser file metadata for the selected CSV.
- Reads the local session only to determine whether the setup flow already has a session.

### Writes

- Sends authentication and registration fields to the approved Backend endpoints.
- Writes the existing browser session record used by the current app shell.
- Does not persist CSV bytes or claim that a server import occurred.

### Must Never Read

- Provider OAuth tokens or authorization codes in the browser.
- Database credentials, backend secrets, or another organization’s data.

### Must Never Write

- Provider tokens, passwords, or raw credentials into rendered UI text.
- CSV content to an unapproved browser or API destination.
- Organization data outside the authenticated Backend scope.

## 10. Security

- Passwords are sent only to the existing Backend auth endpoint and are not stored in React state after the request completes beyond the active form field.
- Access tokens are used for the current application session but are never interpolated into visible status messages, filenames, errors, or logs.
- Organization identity comes from the authenticated Backend response.
- The UI does not accept an organization ID from the URL to establish scope.
- OAuth connectors are status-only until an approved authorization endpoint exists.
- The CSV screen does not upload or expose file contents; it only confirms local selection metadata.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Missing login or registration input | Native required-field validation blocks submission |
| Invalid credentials | Login displays a safe invalid/request failure message |
| Duplicate registration email | Backend error detail is displayed without exposing database details |
| Backend unavailable | Auth screen displays a safe request failure message and remains usable for retry |
| Missing source | Continue displays an alert and keeps the user on setup |
| Non-CSV file | Selection is cleared and the user is asked to choose a CSV |
| Empty CSV | Selection readiness is shown only; server parsing is deferred until the upload contract exists |
| OAuth unavailable | Connector displays availability state only; no secret field is offered |
| Expired/invalid session | Backend `/me` failure prevents session hydration and login reports failure |
| Token or credential error | Token is not rendered; only a generic request failure is shown |

## 12. Testing

### Unit Tests

- Existing frontend tests remain unchanged for the root route behavior.
- Added `tests/entry-flow.test.tsx` to verify that the source setup blocks empty continuation and routes the selected demo path to `/dashboard` while keeping the safe-status notice visible.

### Integration Tests

The intended integrated browser flow is:

1. Open `/login`.
2. Choose `Open demo workspace`.
3. Choose `Load Sawakli demo data`.
4. Continue to `/dashboard`.
5. Confirm that source status is visible and no credential/token text is rendered.

Browser evidence was captured from the running containerized Web service for the login screen and connector/demo setup screen. The screenshots are attached to the QA handoff conversation.

### E2E Impact

The entry routes are new/changed user-facing workflow surfaces. A Playwright or equivalent browser test should be added when the repository’s E2E runner and backend fixture are available.

## 13. Verification

Commands executed:

```bash
cd "D:/projects/Sawakli-AI/apps/web"; npm run type-check
cd "D:/projects/Sawakli-AI/apps/web"; npm ci
cd "D:/projects/Sawakli-AI/apps/web"; npm install --ignore-scripts --no-audit --no-fund
cd "D:/projects/Sawakli-AI"; docker compose up --build -d
cd "D:/projects/Sawakli-AI"; docker compose ps
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
Invoke-WebRequest -UseBasicParsing http://localhost:3000
```

Results:

- `NOT RUN — frontend dependencies unavailable`: host `npm run type-check` could not find `tsc`.
- `FAIL`: host `npm ci` exited with npm error `Exit handler never called!` before installing dependencies.
- `NOT RUN — npm install hung and was terminated after 120 seconds`: the host dependency install remained incomplete.
- `PASS`: `docker compose up --build -d` completed and `docker compose ps` reported API, Web, PostgreSQL, test PostgreSQL, and Worker as healthy.
- `PASS`: `http://localhost:8000/health` returned `{"status":"ok"}`.
- `PASS`: `http://localhost:3000` returned the changed login page with the expected form and demo-workspace link.
- `PASS`: synthetic auth smoke test completed registration, login, and authenticated `/api/auth/me`; the bearer token was not printed.
- `PASS`: CORS preflight for `POST /api/auth/register` returned `200` with `Access-Control-Allow-Origin: http://localhost:3000` after the API middleware fix.
- Editor diagnostics: `PASS` for the touched TypeScript source and test files; this is not a substitute for the project scripts.
- Screenshot evidence: `PASS` — login screen and connector/demo setup screen captured from `http://localhost:3000`.

## 14. Known Limitations

- CSV selection is currently a safe client-side readiness state, not a persisted server import. A CSV upload API contract is required to complete the import.
- Multi-organization selection/switching is not implemented because the current Backend auth contract returns one organization and exposes no organization list endpoint.
- OAuth connector rows show availability but do not initiate provider authorization because no approved frontend/backend OAuth route is present in the current contract.
- Full lint, type-check, unit test, and build remain pending a working host frontend dependency installation. The integrated browser click could not be completed in the shared browser because its reported viewport was `0x0`; API and container smoke checks passed.

## 15. Follow-Up Tasks

- API/Data owner — define and implement the CSV upload/import endpoint, then connect the selected file to staging and normalization.
- API owner — define organization listing/selection and workspace creation semantics for multi-workspace accounts.
- Connector owner — expose the approved OAuth authorization start/callback contract for GA4 and Google Ads.
- UI owner — add Playwright evidence for login, workspace setup, demo/CSV selection, and safe status assertions.

## 16. References and Evidence

- Backend auth schemas: `apps/backend/src/sawakli/api/schemas/auth.py`
- Backend auth routes: `apps/backend/src/sawakli/api/routes/auth.py`
- Auth service: `apps/web/src/services/auth.service.ts`
- Login route: `apps/web/src/app/(auth)/login/page.tsx`
- Workspace setup route: `apps/web/src/app/(auth)/setup/organization/page.tsx`
- Connector setup route: `apps/web/src/app/(auth)/setup/connector/page.tsx`
- Integrated flow test: `apps/web/tests/entry-flow.test.tsx`
- Verification evidence: command output recorded in Section 13
- Screenshots: `PASS` — attached in the QA handoff conversation; captured from the running Web container.
