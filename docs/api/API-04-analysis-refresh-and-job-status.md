# API-04 — Analysis Refresh and Job Status APIs

## 1. Overview

API-04 exposes WORK-01's `jobs` queue to the outside world for the first time, as two HTTP
endpoints:

- `POST /api/analysis/refresh` — queues an analysis job for the caller's organization and
  returns a `job_id` immediately, without waiting on the AI pipeline.
- `GET /api/jobs/{job_id}/status` — reports the current status of a previously queued job.

It exists so the UI's "Refresh Analysis" action has something real to call: a non-blocking
trigger plus a way to poll for completion, instead of a synchronous request that would have to
sit open for however long a full analysis run takes.

It sits in the Backend / API layer, directly on top of API-01 (authentication and
organization-scoping) and WORK-01 (the `jobs` table, the `JobStatus` lifecycle, and the Worker
process that actually claims and executes jobs). API-04 owns the front door to that queue; it
does not own the queue itself, and it never executes or influences AI work directly.

## 2. Scope

### In Scope

- `POST /api/analysis/refresh` — request validation, campaign-ownership checking, and inserting
  a `PENDING` job row (or returning an existing in-flight one).
- `GET /api/jobs/{job_id}/status` — reading and returning a single job's current state, scoped to
  the caller's organization.
- Guaranteeing at most one `PENDING` or `RUNNING` job per organization at a time, including under
  genuinely concurrent requests (new migration `0011_jobs_one_inflight_per_org`).
- A narrow, read-only campaign-ownership check (`db/campaigns_lookup.py`) used only by the
  refresh endpoint.

### Out of Scope

- Campaign management, listing, or metadata (belongs to API-02 — Campaign, Metrics and Dashboard
  APIs).
- Claiming, executing, retrying, or timing out a job once it exists (belongs to WORK-01).
- The AI pipeline itself — feature computation, anomaly detection, forecasting, or recommendation
  generation (AI-01 through AI-06).
- Standardizing the API's error-response shape (belongs to API-07). This task deliberately does
  not adopt the newer nested error format; see Section 7.
- OAuth/token handling of any kind (owned exclusively by the Connector Layer, CONN-02).

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| API-01 — Authentication & Session | Both endpoints depend on `get_auth_context` / `AuthContext` for identifying the caller's user and organization. |
| WORK-01 — Job Claiming and Lifecycle Worker | API-04 reads and writes the same `jobs` table WORK-01 defined and owns; it reuses WORK-01's `JobStatus` enum unchanged. |
| INT-01 — Canonical MVP Contract Pack (PDF) | Defines the endpoint contract this task implements: request/response shape, the duplicate-click requirement, the campaign-ownership requirement (§9.1, item API.5), and the `model_run_id` exclusion (§2.5). No `docs/contracts/` entry exists yet for this — see Section 14. |

No accepted ADR governs this task; none was created for it (see Section 16).

## 4. Architecture

```text
UI "Refresh" click
       ↓
POST /api/analysis/refresh  (API-04)
       ↓
Existing PENDING/RUNNING job for this org?
   ├─ yes → return its job_id, insert nothing
   └─ no  → insert a new PENDING row → return its job_id
       ↓
[ jobs table — WORK-01 owns everything from here on ]
       ↓
Worker process (separate, independent loop — WORK-01)
claims the PENDING row, transitions it through
RUNNING → SUCCESS / FAILED / PARTIAL_SUCCESS / CANCELLED
       ↓
UI polls: GET /api/jobs/{job_id}/status  (API-04)
       ↓
Reads whatever the Worker has written so far
```

Ownership boundary: API-04 only ever **inserts** a `PENDING` row and **reads** job rows. It never
transitions a job's status itself, and never writes to any column other than the ones set at
insert time (see Section 9). Every transition after insertion — claiming, running, completing,
retrying, timing out — belongs exclusively to the Worker (WORK-01), running as a separate process
that this task has no direct dependency on at request time.

## 5. Inputs

**`POST /api/analysis/refresh`**

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `campaign_ids` | `list[UUID] \| None` | No | Request body (`AnalysisRefreshRequest`) | Omitted or `null` means all of the org's campaigns. An explicit empty list (`[]`) is rejected — see Section 7. |
| Bearer token | JWT | Yes | `Authorization` header | Resolved via API-01's `get_auth_context` into the caller's `user` and `organization`; never trusted from any other source. |

**`GET /api/jobs/{job_id}/status`**

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `job_id` | UUID | Yes | URL path | The job to look up. |
| Bearer token | JWT | Yes | `Authorization` header | Same as above. |

## 6. Outputs

**`POST /api/analysis/refresh`** → `202 Accepted`, body `AnalysisRefreshResponse`

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `job_id` | UUID | No | UI | The queued job's id — either newly created, or the id of the job already in flight for this org. |
| `status` | `JobStatus` | No | UI | Always `PENDING` for a request that inserts a new row; reflects the existing job's actual status (`PENDING` or `RUNNING`) when an in-flight job is returned instead. |

**`GET /api/jobs/{job_id}/status`** → `200 OK`, body `JobStatusResponse`

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `job_id` | UUID | No | UI | Echo of the requested id. |
| `status` | `JobStatus` | No | UI | Current status. See Section 7 for which of the type's 7 values are actually observable here. |
| `campaign_ids` | `list[UUID] \| None` | Yes | UI | `None` if the job covers all campaigns. |
| `created_at` | datetime | No | UI | When the job was queued. |

`model_run_id` exists on the underlying `Job` row but is **not** an output of either endpoint —
deliberately excluded per INT-01 §2.5 ("the UI never needs to know `model_run_id` directly").

## 7. Rules and Semantics

**Duplicate-job prevention.** At most one `PENDING` or `RUNNING` job may exist per
`organization_id` at any time. This is enforced twice:

1. **Application-level fast path** — before inserting, the endpoint checks for an existing
   `PENDING`/`RUNNING` job for the org and returns its `job_id` if found. This handles the
   ordinary case (a second click a moment after the first) without ever attempting a duplicate
   insert.
2. **Database-level constraint** — a partial unique index, `uq_jobs_org_inflight`
   (`jobs(organization_id) WHERE status IN ('PENDING','RUNNING')`, added in migration
   `0011_jobs_one_inflight_per_org`), is the actual backstop for the rare case where two requests
   race within the same instant and both pass the application check before either commits. The
   losing insert fails with `IntegrityError`, which the endpoint catches, rolls back, re-queries,
   and returns the winning job's `job_id` — the caller never sees an error from this path.

**`campaign_ids` validation.** Omitted or `null` means "all of the org's campaigns." An explicit
empty list is rejected outright (`422`) by a Pydantic validator — neither "all" nor "none" is a
safe guess for what an empty list was meant to mean. A non-empty list is checked against the
`campaigns` table for organization ownership via `find_missing_campaign_ids()`; any id that
doesn't exist at all, or exists but belongs to a different organization, is treated identically —
both are reported together in a single `422` listing every rejected id.

**Priority.** Every job this endpoint creates is inserted with `priority = "HIGH"`, matching the
existing two-value (`"HIGH"` / `"LOW"`) convention WORK-01's claiming query already uses. No new
priority enum was introduced.

**Status semantics — the 7-vs-6 distinction.** The shared `JobStatus` type has **seven** members:
`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `ERROR`, `PARTIAL_SUCCESS`, `CANCELLED`. `ERROR` is a
legal, non-terminal status in WORK-01's own lifecycle rules — but under the Worker's current
implementation (`worker/scheduler/loop.py::_save_transition`), a proposed `RUNNING → ERROR`
transition is intercepted and immediately rewritten to either `PENDING` (retry, if under
`max_retries`) or `FAILED` (retries exhausted) **before** the row is ever committed. `ERROR` is
therefore never actually persisted to `jobs.status` today, and this endpoint will never return it
in practice, even though the response type technically permits it.

**Org isolation on status lookup.** A job that exists but belongs to a different organization
returns `404` — the same response as a `job_id` that doesn't exist at all. This is a deliberate
choice (see Section 10), not an oversight.

## 8. Public Interfaces

**`POST /api/analysis/refresh`**
*(`sawakli.api.routes.analysis:trigger_analysis_refresh`)*

- **Input:** `AnalysisRefreshRequest { campaign_ids: list[UUID] | None }`
- **Output:** `202 Accepted`, `AnalysisRefreshResponse { job_id: UUID, status: JobStatus }`
- **Errors:** `401` (missing/invalid Bearer token); `422` (explicit empty `campaign_ids` list, or
  a list containing ids not owned by the caller's org)
- **Side effects:** inserts one row into `jobs`, only when no `PENDING`/`RUNNING` job already
  exists for the caller's org. Never calls the AI pipeline. Never blocks on Worker execution.

**`GET /api/jobs/{job_id}/status`**
*(`sawakli.api.routes.jobs:get_job_status`)*

- **Input:** `job_id` (path)
- **Output:** `200 OK`, `JobStatusResponse { job_id, status, campaign_ids, created_at }`
- **Errors:** `401`; `404` (job not found, or belongs to another organization)
- **Side effects:** none — read-only.

Both endpoints depend on API-01's `get_auth_context` (resolves the Bearer token into an
`AuthContext { user, organization }`) and `apply_org_scope` (adds the
`organization_id == caller's org` filter to a query) — neither is re-implemented here.

## 9. Data Ownership

### Reads

- `jobs` — own organization's rows only (via `apply_org_scope` / an explicit
  `organization_id` filter).
- `campaigns` — `id` and `organization_id` columns only, via the read-only
  `campaigns_lookup.find_missing_campaign_ids()` helper. No other column is read.

### Writes

- `jobs` — **insert only**. This task never updates an existing job row. All post-insert
  columns (`status` transitions, `claimed_at`, `retry_count`, `next_retry_at`, `model_run_id`,
  etc.) are written exclusively by the Worker (WORK-01) once a row exists.

### Must Never Read

- `connector_tokens` or any OAuth/token material — owned exclusively by the Connector Layer
  (CONN-02); this task has no access to and no need for token values.
- Any `campaigns` column beyond `id` / `organization_id` — campaign name, budget, platform, etc.
  belong to API-02's domain, not this task's.

### Must Never Write

- `jobs.status`, `jobs.claimed_at`, `jobs.retry_count`, `jobs.next_retry_at`,
  `jobs.model_run_id`, or any other field on an existing job row — all Worker-owned post-insert.
- `campaigns` — read-only reference only; this task has no write path to it at all.

## 10. Security

- Both endpoints require a valid Bearer JWT resolved through API-01's `get_auth_context`; there
  is no anonymous or unauthenticated path.
- Full organization isolation on both endpoints. `organization_id` is always taken from the
  resolved `AuthContext`, never from client-supplied input — a caller cannot specify which
  organization's job to create or read.
- The status-lookup endpoint returns `404` (not `403`) for a job belonging to another
  organization, identical to a nonexistent `job_id`. This is a deliberate anti-enumeration
  choice: confirming that a given `job_id` exists at all, even without exposing its contents,
  is itself information a caller outside that organization should not be able to obtain.
- Client-supplied `campaign_ids` are validated against organization ownership before being
  trusted for anything — an organization cannot reference another organization's campaign ids to
  influence what gets analyzed.
- No secrets, credentials, or tokens are read, written, or exposed anywhere in this task.
- Database role: queries run under whatever role the API process already connects as; this task
  introduced no new database roles, grants, or permission changes.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Missing input (`campaign_ids` omitted) | Treated as "all of the org's campaigns" — not an error. |
| Malformed input (`campaign_ids: []`, explicit empty list) | `422`, rejected by a Pydantic validator before any database query runs. |
| Malformed input (`campaign_ids` referencing another org's campaigns, or nonexistent ids) | `422`, listing exactly which ids were rejected. |
| Missing/invalid auth | `401`. |
| Zero values | N/A — this task performs no numeric aggregation or division. |
| Insufficient data | N/A — no minimum-data threshold applies to queuing a job. |
| Duplicate records (double-click or concurrent refresh) | Same `job_id` returned; no duplicate row is created. Enforced by the application-level check first, then the database's partial unique index for genuine races (see Section 7). |
| Database failure | Not explicitly handled by this task — propagates as an unhandled `500`, consistent with every other existing route in this codebase (no global exception handler exists anywhere in the API yet). |
| Provider or API failure | N/A — this task never calls an external provider; that belongs to the Connector Layer and AI Layer respectively. |
| Timeout | N/A at this task's layer — request handling is a handful of fast queries. A stuck `RUNNING` job's timeout is WORK-01's `timeout_seconds` / timed-out-job recovery logic, not this task's. |
| Cancellation | N/A — this task exposes no cancel action. `CANCELLED` is a status this endpoint can report but never sets. |
| Unknown `job_id` (status lookup) | `404`. |
| Job belonging to another organization (status lookup) | `404` — identical to unknown, per Section 10. |

## 12. Testing

### Unit Tests

N/A — no pure-unit (mocked-dependency) tests were added for this task. Every test exercises the
real FastAPI application end-to-end against a live PostgreSQL database via the existing
`client` / `db_session` fixtures, consistent with how this codebase's other API-layer tests
(`test_auth.py`, `test_org_isolation.py`) are already structured. There is no unit/integration
split for this layer's tests today.

### Integration Tests

`tests/test_analysis_refresh.py` (11 tests) and `tests/test_job_status.py` (8 tests), all run
against a real PostgreSQL 16 instance. What they actually establish:

- An authenticated refresh with no `campaign_ids` creates a `PENDING` job scoped to the caller's
  org, with `priority = "HIGH"` and `model_run_id = None`.
- A refresh scoped to specific, org-owned `campaign_ids` stores them correctly on the job.
- `campaign_ids` belonging to a different organization, or that don't exist, are both rejected
  with `422`.
- An explicit empty `campaign_ids` list is rejected with `422`.
- Two refresh calls while a job is still `PENDING` return the same `job_id`, and exactly one row
  exists afterward.
- Two different organizations refreshing at the same time do **not** dedupe against each other.
- Once a job reaches a terminal status (`SUCCESS`), a further refresh creates a genuinely new job.
- **8 genuinely concurrent refresh requests** (via `ThreadPoolExecutor`) against the same
  organization create **exactly one** job — stress-run 5 times in isolation, all 5 clean, to rule
  out flakiness rather than relying on a single pass.
- Neither response ever includes `model_run_id`.
- The status endpoint reflects live database state across multiple manually-driven transitions
  (`PENDING` → `RUNNING` → `SUCCESS`), not a cached value.
- An unknown `job_id` and a `job_id` belonging to another organization both return `404`.
- `campaign_ids` round-trips correctly through JSONB storage and back into the response.
- Unauthenticated requests to either endpoint return `401`.

### E2E Impact

Gives the frontend a real Refresh button and status-polling target to build against for the
first time. No automated browser-level end-to-end test exists yet for this flow — UI work on it
had not started as of this document.

## 13. Verification

Commands executed (local verification environment: Ubuntu 24, Python 3.12, PostgreSQL 16,
`sawakli_test` database):

```bash
pip install -e ".[dev]"
alembic upgrade head
pytest -q
ruff check .
ruff format --check .
mypy src
alembic downgrade -1   # migration round-trip check
alembic upgrade head   # re-applied, confirmed index restored
pytest tests/test_analysis_refresh.py::test_concurrent_refresh_requests_create_only_one_job -q   # x5, isolated
pytest -q   # full suite, re-run twice back-to-back
```

Results:

- `alembic upgrade head` (pre-merge, local branch, 2026-08-26) — **PASS**. Migration `0011`
  applied cleanly; a first attempt with a longer revision id failed on
  `alembic_version.version_num`'s `VARCHAR(32)` limit and rolled back with zero partial state
  (transactional DDL) — fixed by shortening the revision id, then re-run clean.
- `pytest -q` (pre-merge, local branch, 2026-08-26) — **PASS**. `111 passed, 7 skipped` (baseline
  before this task: `92 passed, 7 skipped` — the 7 skips are pre-existing and unrelated to this
  task).
- `ruff check .` — **PASS**. All checks passed.
- `ruff format --check .` — **PASS**. 102 files already formatted.
- `mypy src` (strict) — **PASS**. No issues found in 65 source files.
- Migration round-trip (`downgrade -1` → `upgrade head`) — **PASS**. Index confirmed absent after
  downgrade and present again after re-upgrade, via `\d jobs`.
- Concurrency test, run 5× in isolation — **PASS** (5/5). No flakiness observed.
- Full suite, run twice consecutively — **PASS** (both runs `111 passed, 7 skipped`, no test
  pollution between runs).
- **Post-merge re-verification** (2026-08-26, same day) — pulled the actual merged `main` branch
  fresh (not the pre-merge local branch), reinstalled dependencies from scratch, and reran the
  full pipeline above against that exact merged state: `alembic upgrade head` — **PASS**;
  `pytest -q` — **PASS**, `111 passed, 7 skipped`, identical to pre-merge; `ruff check .` —
  **PASS**; `ruff format --check .` — **PASS**; `mypy src` — **PASS**.
- **CI run / pull request evidence:** GitHub Actions ("Sawakli AI CI") on PR #6, commit `c94ba84`
  — **PASS**. Three jobs (Backend, Frontend, Integration) all green. The workflow did not
  trigger on initial PR open; reopening the PR triggered it. Root cause not confirmed — requires
  repository Settings access to investigate.
- **NOT RUN — local reproduction on Mohamed's machine.** Python 3.13 was active (project
  requires `>=3.12,<3.13`) and no local PostgreSQL was running at the time. Verified instead in
  the environment above and independently via GitHub Actions.

## 14. Known Limitations

- **`ERROR` and the in-flight constraint.** The one-job-per-org index (`uq_jobs_org_inflight`)
  and this endpoint's own in-flight check both cover only `PENDING` and `RUNNING`. `ERROR` is a
  legal, non-terminal status in WORK-01's lifecycle rules (`RUNNING → ERROR` is allowed), but
  under the Worker's current implementation it is never actually persisted — a proposed `ERROR`
  transition is rewritten to `PENDING` or `FAILED` before being committed (see Section 7). If that
  Worker-side behavior ever changes such that `ERROR` becomes a persisted, resting status, this
  endpoint's in-flight check would need revisiting, since a job resting in `ERROR` would not
  currently block (or be surfaced as) an in-flight job.
- **No global exception handler.** A database failure during either endpoint surfaces as a plain
  unhandled `500`. This is true of every route in the API today, not specific to this task, but
  it applies here too.
- **The campaign-ownership check is a stand-in.** `db/campaigns_lookup.py` is a deliberately
  narrow, read-only helper built because API-02 (the real Campaign Data API) doesn't exist yet.
  It should be reconciled with or replaced by API-02's own model once that task lands, not
  duplicated indefinitely.
- **No canonical `docs/contracts/` entry exists yet** for the INT-01 API contract or the
  `JobStatus` enum this task depends on — both currently live only in the original PDF contract
  pack. This document links to that PDF as the best available source; the gap in `docs/contracts/`
  is not something this task created or is positioned to fix.
- **Documentation timing.** Written after PR #6 merged, not in the same PR as the
  implementation — the task-documentation requirement took effect after this task shipped.

## 15. Follow-Up Tasks

- `API-02` — owner TBD — replace `campaigns_lookup.py`'s narrow ownership check with the real
  Campaign model once built; do not maintain both.
- `API-07` — Youssef — adopt the standardized nested error-response format for these two
  endpoints (and every other existing route) once that task starts. Deliberately not done here,
  to avoid a second, inconsistent error format existing in the meantime.
- WORK-01 owner — consider whether a job resting in `ERROR` should also count toward the
  "one in-flight job per org" rule, given `ERROR` is a legal (if currently unobserved) non-terminal
  status in the job lifecycle.

## 16. References and Evidence

- Notion task: API-04 — Implement Analysis Refresh and Job Status APIs (Base Points: 4;
  Category: Web; Due: August 28, 2026)
- Pull request: `#6`, branch `api-04-refresh-and-job-status` → `main`; merge commit `19c0cd4`
  (2026-08-26 20:22:48 +0400); feature commit `c94ba84`; post-merge cleanup commit `84b246d`
  (removed a stray debug-output file accidentally swept in by `git add -A`); 10 files changed,
  723 insertions, 2 deletions.
- Canonical contracts: INT-01 Canonical MVP Contract Pack (PDF) — §2.1 (endpoint table), §2.5
  (`model_run_id` exclusion), §9.1 item API.5 (campaign-ownership requirement). No
  `docs/contracts/` entry exists yet; see Section 14.
- ADRs: N/A — no ADR exists for the in-flight-job constraint or the campaign-ownership stand-in;
  both are recorded here and in the PR description only.
- Related technical documentation: `Sawakli_AI_Project_Log.md`, Section 21 (narrative account of
  this task); `Sawakli_AI_Weekly_Update_CONN01_CONN02_API04.pdf` (presentation-facing summary
  covering this task alongside CONN-01 and CONN-02).
- Test or CI evidence: see Section 13.
