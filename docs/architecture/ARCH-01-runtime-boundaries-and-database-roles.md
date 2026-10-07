# ARCH-01 — Reconcile Runtime Boundaries and Database Roles

| Item | Lifecycle |
|---|---|
| Decision record [ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md) | `Proposed`; accepted at the weekly team review |
| Migration log masking in `apps/backend/alembic/env.py` | `Implemented` in this task's pull request |
| Runtime logins, successor grants, Compose/CI split, request-scoped organization context | Not implemented; follow-ups in §15 |

## 1. Overview

ARCH-01 settles the unresolved runtime boundaries and database privilege decisions of the Sawakli AI
modular monolith. It compares how each runtime process connects to PostgreSQL today with the
least-privilege intent of migration `0007_security_roles_grants_rls` and INT-01 v1.1. It then
publishes a bounded decision record (ADR 0001) and names the owners of every affected contract and
follow-up.

This document is the evidence record. It contains:

- the static inventory;
- the live audit of roles, grants and row-level security (RLS) on a throwaway database;
- the least-privilege probes;
- the verdicts on the audit leads;
- the one code change; and
- verification.

The decisions, the intended per-process privilege matrix, the boundary delta and the
fixture/contract delta are defined in [ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md)
and are not repeated here.

## 2. Scope

### In Scope

- Inventory of how Web, API, Worker, migrations, CI and tests connect to PostgreSQL: user,
  configuration, secrets received, and in-process modules.
- Live audit of roles, memberships, table and column grants, RLS, policies, default privileges and
  `SECURITY DEFINER` functions on a throwaway database built from migrations.
- Least-privilege probes under logins that model the `0007` bundles exactly as written.
- The intended per-process matrix, the boundary delta against INT-01 v1.1 and `0007`, and the
  fixture/contract delta (in ADR 0001).
- Confirmed follow-up defects with proposed owners, reviewers and affected files.
- Masking the database password in the Alembic log (TRK-06 register D-16).

### Out of Scope

| Topic | Owner |
|---|---|
| Upload request/response, transaction boundary, error envelope, migration coordination, schema reviewer | ARCH-02 (Ahmed Ibrahem) |
| AI input, run and persistence interfaces; `feature_daily` vs `daily_metrics` | ARCH-03 (Hussein Elhaddad) |
| `RawResponse` persistence, Connector parsing vs Data writes, `data_sources` status and freshness, provider credentials | ARCH-04 (Youssef Halawa) |
| Worker dispatch, job and model-run transitions, how the Worker sets organization context per job | ARCH-05 (El-Farouk Omar) |
| Frontend API client and state | ARCH-06 (Abdulrahman Ehab) |
| Contract validators, CI harness, `TEST_DATABASE_URL`, dependency pinning | QA-00 (Mohamed Hassan) |
| Organization-isolation and secret-table tests | AI-07 (Hussein Elhaddad); QA-05 (Mohamed Hassan) |
| Building runtime logins, a successor grants migration, Compose/CI changes, request-scoped organization context code | No task card; recorded as a plan gap (ADR 0001 §10) |

This task changes no migration, Compose or CI file, `db/session.py`, route, Worker code,
`tests/contracts/` fixture, INT-01 text or legacy directory.

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| TRK-06 — Review Integrated Baseline and Present Evidence Register (Done, 30 September 2026) | The ARCH-01 card's "Depends On (2026-09)" field names TRK-06, and its Completion Gates state "Final acceptance requires: TRK-06". The register's D-16 and D-26 findings feed this task. |
| W2 joint interface review | Named in the ARCH-01 Entry Contract ("TRK-06 baseline plus W2 joint interface review"). Whether it has taken place is **Unverified**: no record exists in the repository or the board export. |
| INT-01 Canonical MVP Contract Pack v1.1 | Governing contract for table ownership (§1, §3) and layer interactions (§2.2–§2.9). |
| Migration `0007_security_roles_grants_rls` | Defines the six permission bundles, grants and RLS policies under review. |
| `README.md` architecture section | Defines the four-service modular-monolith runtime. |

The card field name "Depends On (2026-09)" is quoted verbatim. The terminology conflict between
`docs/AGENTS.md:48-49` and the board is recorded as TRK-06 register D-01 and is not resolved here.

ADRs: none existed before this task. This task adds
[ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md) with status `Proposed`.

## 4. Architecture

### Runtime processes and database identity today

```text
Web (Next.js) ──HTTP──▶ API (FastAPI: Backend + Connector + Data code) ──┐
                                                                         ├──▶ PostgreSQL (as postgres)
Worker (Python: Worker code) ────────────────────────────────────────────┘
Alembic (local, CI backend job, CI integration job via the api container) ──▶ PostgreSQL (as postgres)
```

| Process | Database user | Configured at | Secrets received | Database-touching modules in the process |
|---|---|---|---|---|
| Web | None | `docker-compose.yml:78-96` (environment holds only API URLs); `apps/web` has no database client | None | None |
| API | `postgres` (bootstrap superuser) | `docker-compose.yml:42`; fallback default `db/session.py:34-37` | `DATABASE_URL` including password, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `CORS_ALLOWED_ORIGINS` (`docker-compose.yml:41-45`) | Backend, Connector (CSV parsing only, no database access), Data (upserts) |
| Worker | `postgres` | `docker-compose.yml:64` | `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES` (`docker-compose.yml:63-66`); Worker code reads no JWT setting | Worker |
| Alembic (local) | User in `DATABASE_URL`; environment overrides `.env` | `alembic/env.py:10-39` | `DATABASE_URL` | All DDL and the demo seed (`0009`) |
| CI backend job | `postgres` | `.github/workflows/ci.yml:33-35` (service), `:61` (pytest), `:66` (Alembic) | `DATABASE_URL`, `JWT_SECRET` | Test suite and migrations |
| CI integration job | `postgres`, through the API container | `.github/workflows/ci.yml:109` → `docker-compose.yml:42` | API container environment | Migrations run with the API runtime identity |
| pytest (local default) | `postgres` | `tests/conftest.py:23-27`; migrations run by the same identity at `tests/conftest.py:31-35` | `DATABASE_URL`, `JWT_SECRET` defaults | Test suite and migrations |

### Module database access today

| Module (process) | Reads | Writes | Evidence |
|---|---|---|---|
| Backend (API) | `users`, `organizations`, `organization_members`; `jobs`; `campaigns` (ownership check); `data_sources` | `users`, `organizations`, `organization_members` (registration); `jobs` (insert); `data_sources` (insert; `sync_status`, `last_error`; `status`, `sync_status`, `last_synced_at`, `last_error`); `raw_api_responses` (insert, route-level SQL) | `api/routes/auth.py:40-63,81-88`; `api/deps.py:59-66`; `api/routes/analysis.py:26-35,71-100`; `api/routes/jobs.py:36,54-59`; `db/campaigns_lookup.py:37-43`; `api/routes/connectors.py:46-58,62-68,75-81,133-147,153-160` |
| Data (API) | Upsert `RETURNING` ids | `campaigns`, `ad_groups`, `ads`, `creatives`, `daily_metrics`, `ga_events`; sets `app.current_org_id` | `data/normalization/upsert.py:27-32,63-264`, called from `api/routes/connectors.py:152` |
| Connector (API) | None at runtime | None at runtime | `PostgresTokenRepository` (`connectors/oauth/repository.py:90-162`) has no runtime caller; only `tests/integration/connectors/oauth/test_postgres_repository.py` uses it |
| AI (no runtime caller) | `DatabaseDataLoader` reads `daily_metrics` and `campaigns`; no runtime caller | None | `ai/features/loaders.py:50-121`; `ai/pipeline.py` is empty |
| Worker (Worker) | `jobs` | `jobs.status`, `retry_count`, `next_retry_at`, `claimed_at` | `worker/jobs/claim.py:9-28`; `worker/scheduler/loop.py:22-45,50-74,77-103,129-130`; the executor is a simulation (`worker/orchestration/execute.py:8-30`) |

The intended per-process identities and bundle memberships are defined in
[ADR 0001 §5](../adr/0001-runtime-boundaries-and-database-roles.md#5-decision).

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| Repository at `e5806de` | Git tree | Yes | `origin/main` | Code, migrations, Compose, CI and tests audited |
| INT-01 v1.1 | PDF | Yes | Notion export, 4 October 2026 | Governing contract; §1, §2.2–§2.9, §3, §6. Pages 1–11 have no text layer and were read as page images. |
| Task cards | Markdown | Yes | Notion export, 4 October 2026 | ARCH-01 to ARCH-06, AI-07, QA-05, QA-00, ING-01, WORK-03, WORK-04, DATA-01, API-01 |
| Board properties | CSV | Yes | `📋 Tasks …_all.csv` in the same export | Status and owners |
| Throwaway database | PostgreSQL 18.6 | Yes | Local `postgres:18` container on port 5440, built by `alembic upgrade head` | Live audit and probes; destroyed after use |

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| [ADR 0001](../adr/0001-runtime-boundaries-and-database-roles.md) | Markdown | No | Team review; ARCH-02 to ARCH-06; follow-up owners | Decision record, intended matrix, boundary delta, fixture/contract delta, follow-ups |
| This document | Markdown | No | Reviewers; QA-00, AI-07, QA-05 | Evidence record |
| `apps/backend/alembic/env.py` | Python | No | Anyone running Alembic | The migration log prints the database URL with the password masked |
| `docs/README.md` links | Markdown | No | Readers of `docs/` | Links to the ADR and this document |

## 7. Rules and Semantics

### Privilege model semantics

- **Bundle:** one of the six `NOLOGIN` roles from `0007`. A **runtime login** inherits bundles by
  membership (`rolinherit=true` and `inherit_option=true` were observed for the probe logins).
- **Cell states** used in ADR 0001:
  - `Required now`: current code needs the privilege.
  - `Conditional — ARCH-0x`: depends on an undecided neighbouring decision.
  - `Not granted`: deliberately withheld.
  - `Not applicable`: the process is not a database principal for that bundle.
- **RLS semantics observed:**
  - All 14 policies are `PERMISSIVE`, `FOR ALL`, `TO public`, with a `USING` expression only.
  - With no `WITH CHECK`, the `USING` expression also checks inserted and updated rows.
  - `get_current_org_id()` returns `NULL` when `app.current_org_id` is unset, so no row matches
    (fail-closed).
  - Superusers bypass RLS even when it is forced. A non-superuser table owner bypasses RLS unless
    `FORCE ROW LEVEL SECURITY` is set (§13).
- **Transaction-local context:** `set_config('app.current_org_id', <org>, true)` lasts until the
  end of the current transaction (PostgreSQL `set_config` with `is_local = true`).

### Current state (live audit, fresh build at `e5806de`)

- **Roles:**
  - `postgres` is `rolsuper`, `rolbypassrls` and `rolcanlogin`.
  - The six bundles are `NOLOGIN NOSUPERUSER NOBYPASSRLS`.
  - No role memberships exist.
- **Ownership and RLS:** `postgres` owns all 24 tables, 3 views and 1 sequence. RLS is enabled on
  14 tables and forced on none.
- **Default privileges:** `pg_default_acl` is empty.
- **Unrestricted defaults:** `get_current_org_id()` is `SECURITY DEFINER`, owned by `postgres`,
  with the default `EXECUTE` for `PUBLIC` and no pinned `search_path`. `CONNECT` and `TEMP` on the
  database are the `PUBLIC` defaults.
- **Metadata tables:** `alembic_version`, `schema_migrations` and `schema_version` have no grants.

Effective bundle privileges per table:

| Table | backend | data_layer | ai_layer | connector | worker | readonly |
|---|---|---|---|---|---|---|
| `action_simulations` | S | – | SIUD | – | – | S |
| `ad_groups` | S | SIUD | – | – | – | S |
| `ads` | S | SIUD | – | – | – | S |
| `alembic_version` | – | – | – | – | – | – |
| `anomalies` | S | – | SIUD | – | – | S |
| `campaigns` | S | SIUD | S | – | – | S |
| `connector_tokens` | – | – | – | SIUD | – | – |
| `creatives` | S | SIUD | – | – | – | S |
| `daily_metrics` | S | SIUD | S | – | – | S |
| `data_sources` | SI | S u | – | S | S | S |
| `execution_logs` | SIUD | – | – | – | – | S |
| `feature_daily` | S | SIUD | S | – | – | S |
| `forecasts` | S | – | SIUD | – | – | S |
| `ga_events` | S | SIUD | – | – | – | S |
| `jobs` | SIUD | – | – | – | S u | S |
| `model_runs` | S | – | SIUD | – | SI | S |
| `oauth_connections` | SIUD | – | – | – | – | S |
| `organization_members` | SIUD | – | – | – | – | S |
| `organizations` | SIUD | – | – | – | S | S |
| `raw_api_responses` | S | SIUD | – | – | – | S |
| `recommendations` | S u | – | SI | – | – | S |
| `schema_migrations` | – | – | – | – | – | – |
| `schema_version` | – | – | – | – | – | – |
| `users` | SIUD | – | – | – | S | S |

S = `SELECT`, I = `INSERT`, U = `UPDATE`, D = `DELETE`; u = column-level `UPDATE` only, namely:

- `data_sources`: `status`, `sync_status`, `last_synced_at`, `last_error` (data_layer);
- `jobs`: `status`, `model_run_id` (worker);
- `recommendations`: `status` (backend).

### Grant drift (listed only; no migration in this task)

| # | Drift | Evidence |
|---|---|---|
| G1 | `worker_role` has no `UPDATE` on `jobs.claimed_at` (added in `0010_auth_and_jobs_additions.py:26-29`), `retry_count` or `next_retry_at` (added in `0011_jobs_retry_timeout_error.py:101-112`). The Worker writes all three. | `0007:175`; `worker/scheduler/loop.py:23,31,130`; probe P2 |
| G2 | No default privileges exist, so tables from future migrations receive no bundle grants. | `pg_default_acl` empty |
| G3 | Objects created after `0007` have no grants: `schema_version`, `schema_version_id_seq`, `v_role_permissions`, `v_schema_inventory`, `v_index_inventory`. No runtime code uses them. | Live audit |
| G4 | Columns added after `0007` inherit table-level grants; only column-scoped grants miss them (G1). | `has_column_privilege`: `backend_role` `UPDATE` on `jobs.retry_count` is true; `readonly_role` `SELECT` on `users.name` is true |
| G5 | All policies are `TO public`; no `worker_role`-scoped policy exists, although the Worker scans `jobs` across organizations in the claim, running-job and timeout queries. | `0007:262-263`; `worker/jobs/claim.py:9-28`; `worker/scheduler/loop.py:50-60,77-103`; probe P1 |
| G6 | `0007` grants more than INT-01 §1.1, §2.2 and §3 allow (list in ADR 0001 §8). | `0007:81-109,143-149,178-179` |
| G7 | `ad_groups`, `ads` and `creatives` have neither an `organization_id` column nor RLS; `connector_tokens`, `users`, `organizations` and `organization_members` rely on grants only. | Live audit |
| G8 | `get_current_org_id()` is `SECURITY DEFINER` without a pinned `search_path`; its body does not need definer rights. | `0007:220-227`; live audit |
| G9 | The CSV upload path in the API process writes Data-owned tables and `data_sources` status columns that `backend_role` cannot write. | `api/routes/connectors.py:62-68,133-160`; probe P3; TRK-06 D-24 |

## 8. Public Interfaces

The only externally observable change is the Alembic log line printed by `apps/backend/alembic/env.py`:

| Before | After |
|---|---|
| `ALEMBIC DATABASE: postgresql+psycopg://<user>:<password>@<host>/<db>` (password in clear) | `ALEMBIC DATABASE: postgresql+psycopg://<user>:***@<host>/<db>` |

- **How:** the URL is rendered with SQLAlchemy `make_url(...).render_as_string(hide_password=True)`.
- **Moved print:** the print now runs after the `if not database_url` check, so it is never called
  on `None`. Before the change, the URL was printed before validation, and an unset `DATABASE_URL`
  printed `None`.
- **Unchanged:** reading and validating `DATABASE_URL`, the `RuntimeError` message, and the
  connection behaviour.

No REST endpoint, function signature, table, column, grant or policy changes.

## 9. Data Ownership

### Reads

- Repository contents at `e5806de`.
- The Notion export of 4 October 2026 (cards, board CSV, INT-01 v1.1 PDF).
- Throwaway local PostgreSQL databases.

### Writes

- `apps/backend/alembic/env.py`: the masked log line.
- ADR 0001, this document, and two links in `docs/README.md`.
- Throwaway local databases only. Two probe logins (`arch01_probe_api` in `backend_role`,
  `arch01_probe_worker` in `worker_role`) and synthetic organizations, users and jobs existed only
  there, and were destroyed with the containers.

### Must Never Read

- Real credentials, `.env` content, team or production databases. No repository-root `.env` exists
  in the audited clone.

### Must Never Write

- Team Compose volumes.
- Migrations, Compose, CI, `db/session.py`, routes, Worker code and `tests/contracts/`.
- INT-01, Notion and the legacy root directories.

## 10. Security

- **Runtime identity:** API and Worker run as a superuser with `BYPASSRLS`. Every grant and RLS
  policy in `0007` is therefore inert at runtime (lead L6; control probes in §13).
- **Secret table:** `connector_tokens` is readable by every database-connected process today. Under
  `backend_role` it is denied (probe P6). Inside a process, module-level separation is an accepted
  limitation (ADR 0001 D1).
- **Organization isolation:** under the bundles, RLS fails closed. Reads without organization
  context return no rows, and writes without context are rejected (probes P3b, P4, P5).
  Application-level `organization_id` filters remain mandatory (INT-01 §3 hard rule).
- **Secrets in logs (fixed):** before this change, `alembic/env.py` printed the database password on
  every migration run, including CI and the pytest migration fixture (TRK-06 D-16). After the change,
  the line shows `***`.
- **Secret distribution:**
  - Compose forwards `JWT_SECRET` to the Worker, which does not use it.
  - Compose passes `CONNECTOR_TOKEN_ENCRYPTION_KEY` to no process (ADR 0001 FU-07).
  - The runtime falls back to a hard-coded superuser connection string when `DATABASE_URL` is
    unset (ADR 0001 FU-08).
- **Probe hygiene:** probes used synthetic organizations, users, JWT secret and passwords, on local
  throwaway containers only. No credential value appears in this document. Connection strings are
  written as `postgresql+psycopg://<user>:<password>@<host>/<db>`.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Missing input: `DATABASE_URL` unset and absent from `.env` | `RuntimeError` with the existing message, raised before anything is printed |
| Malformed input: unparsable `DATABASE_URL` | SQLAlchemy raises `ArgumentError` at the print. The message does not echo the input string (checked with SQLAlchemy 2.0.53). Before the change, the raw string was printed first. |
| URL without a password | Printed unchanged; there is nothing to mask |
| Percent-encoded password | Parsed by `make_url` and masked as `***` |
| Zero values | N/A — no numeric computation in this task |
| Insufficient data | N/A — no analytical computation in this task |
| Duplicate records | N/A — the change writes no data |
| Database failure | Unchanged — connection errors surface from `create_engine(...).connect()` as before |
| Provider or API failure | N/A — no provider or HTTP call is involved |
| Timeout | N/A — no timeout behaviour is changed |
| Cancellation | N/A — no cancellable operation is involved |
| Runtime under the `0007` bundles (observed, not changed) | Fail-closed reads return empty lists or `404 Not Found`. Rejected writes raise `InsufficientPrivilege` (SQLSTATE `42501`): "permission denied" or "new row violates row-level security policy". Details in §13. |

## 12. Testing

### Unit Tests

- **None added.** `alembic/env.py` is a module-level script that runs only inside Alembic's
  environment context; it cannot be imported in isolation.
- **Why the run evidence suffices:** the change is a single call to SQLAlchemy's
  `render_as_string(hide_password=True)`, so a unit test would test SQLAlchemy rather than
  repository behaviour. Verification relies on executed migration runs (§13).

### Integration Tests

- The existing pytest suite runs `env.py` through the `migrated_database` fixture
  (`tests/conftest.py:31-35`) and passed against a fresh database (§13).
- The least-privilege probes (§13) are audit evidence, not repository tests. The repository has no
  test that connects as a non-superuser (lead L4). Adding such tests is a follow-up for QA-00,
  AI-07 and QA-05 (ADR 0001 FU-09).

### E2E Impact

- None. No runtime path changes.

## 13. Verification

### Repository checks

Commands executed from `apps/backend` on 4 October 2026, on Windows 10 with Python 3.12.10 and
SQLAlchemy 2.0.53:

```bash
ruff check .
ruff format --check .
mypy src
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5440/sawakli pytest
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5440/sawakli alembic upgrade head
```

Each database command ran against its own fresh throwaway container:

```bash
docker run --rm -d --name arch01-pg -e POSTGRES_PASSWORD=<local-synthetic> -e POSTGRES_DB=sawakli -p 5440:5432 postgres:18
```

| Check | Result |
|---|---|
| `ruff check .` | PASS — "All checks passed!" |
| `ruff format --check .` | PASS — "150 files already formatted" |
| `mypy src` | PASS — "Success: no issues found in 88 source files" |
| `pytest` (fresh container) | PASS — 233 passed, 9 skipped. The 9 skips are the real-PostgreSQL tests gated on `TEST_DATABASE_URL`, which was left unset to match CI (TRK-06 D-15). |
| `alembic upgrade head` (fresh container) | PASS — 14 revisions applied to head `0012_entity_unique_indexes`; log line `ALEMBIC DATABASE: postgresql+psycopg://postgres:***@localhost:5440/sawakli`; 0 occurrences of the password |
| `alembic upgrade head` before the change | The log contained the password once (the `env.py` print). The line is not reproduced. |
| Documentation governance (`.github/scripts/check-documentation-governance.sh`) | Recorded in the pull request; the check compares committed revisions |
| CI | Recorded in the pull request against its head SHA |

### Live audit procedure

On a fresh throwaway database migrated as the superuser, the audit queried:

- `pg_roles` and `pg_auth_members`;
- `pg_class` (owner, `relrowsecurity`, `relforcerowsecurity`);
- `aclexplode` over table and column ACLs;
- `pg_policies`;
- `pg_default_acl`;
- `pg_proc` (`prosecdef`, owner, ACL);
- `has_table_privilege`, `has_column_privilege` and `has_any_column_privilege` for each bundle × table.

Two independent fresh builds produced identical output. Results are summarized in §7.

### Least-privilege probes

**Setup**

- **Logins:** `arch01_probe_api` (`LOGIN NOSUPERUSER NOBYPASSRLS IN ROLE backend_role`) and
  `arch01_probe_worker` (`LOGIN NOSUPERUSER NOBYPASSRLS IN ROLE worker_role`). They model the
  `0007` bundles exactly as written and are not a proposal.
- **Seed (as superuser):** three organizations, each with one user. Organizations A and B each have
  a CSV data source, campaigns, daily metrics and one `PENDING` job. This is in addition to the
  `0009` demo organization.
- **Approach labels:**
  - "real code": the repository function or route, called through FastAPI `TestClient` with the
    session bound to the probe login.
  - "exact SQL": the statement from the cited line.

| Probe | Login | Approach | Result |
|---|---|---|---|
| P1a | worker | Real code: `claim_next_job()` (`worker/jobs/claim.py:9-28`) | 0 jobs visible while 2 `PENDING` jobs exist; nothing claimed |
| P1b | worker | Real code: `run_once(db)` (`worker/scheduler/loop.py:106-169`) | Returns `[]`; no error is raised |
| P2a | worker | Real code: `run_once(db)` with organization A context set by the probe | `permission denied for table jobs` at commit (the `claimed_at` write, `loop.py:130`) |
| P2b | worker | Exact SQL: `UPDATE jobs SET status` (organization A context) | 1 row updated |
| P2c | worker | Exact SQL: `UPDATE jobs SET retry_count`, `next_retry_at`, `claimed_at` (each separately) | `permission denied for table jobs` (42501) for each |
| P3a | api | Real code: `POST /api/connectors/csv/{id}/upload` | `404` "Data source not found": RLS hides the source at the ownership read (`connectors.py:99-101`), so no write is reached |
| P3b | api | Real code: `POST /api/connectors/setup` | `new row violates row-level security policy for table "data_sources"` |
| P3c | api | Exact SQL: `INSERT INTO raw_api_responses` (`connectors.py:133-147`, organization context set) | `permission denied for table raw_api_responses` |
| P3d | api | Real code: `normalize_and_upsert_batch()` (`data/normalization/pipeline.py:94-99`) | `permission denied for table campaigns` |
| P3e | api | Exact SQL: `UPDATE data_sources` status columns (`connectors.py:153-160`, context set) | `permission denied for table data_sources` |
| P3f | api | Exact SQL: `UPDATE data_sources` failure columns (`connectors.py:62-68`, context set) | `permission denied for table data_sources` |
| P4a | api | Real code: `POST /api/analysis/refresh` | `new row violates row-level security policy for table "jobs"` |
| P4b | api | ORM insert as in `analysis.py:71-88`, no context | `new row violates row-level security policy for table "jobs"` |
| P4c | api | Same insert after `set_config('app.current_org_id', <org>, true)` | Succeeds; 1 row visible |
| P5a | api | `SELECT` on `campaigns`, no context | 0 rows |
| P5b | api | `SELECT` on `campaigns`, organization A context | 2 rows, all organization A |
| P6a | api | Exact SQL: `SELECT` on `connector_tokens` | `permission denied for table connector_tokens` |
| P6b | api | Real code: `PostgresTokenRepository.get()` (`connectors/oauth/repository.py:108-131`) | `permission denied for table connector_tokens` |
| E1 | api | Real code: `GET /api/auth/me` | `200`; the authentication tables have no RLS |
| E2 | api | Real code: `GET /api/jobs` | `200` with `[]` although the organization has a job |
| E3 | api | Real code: `GET /api/jobs/{own job}/status` | `404` "Job not found" for the caller's own job |
| P7a | api | Real code: `POST /api/analysis/refresh`, context set once at the start of the request | The job row commits, then `InvalidRequestError: Could not refresh instance` at `analysis.py:100` (new transaction without context) |
| P7b | api | Same route, context re-applied on every transaction | `202 Accepted` |
| Owner | non-superuser table owner | Exact SQL on a throwaway RLS table | Owner reads the row with RLS enabled; 0 rows once `FORCE ROW LEVEL SECURITY` is set; a superuser reads it even when forced |
| Control | `postgres` | P1–P6 as the superuser | All succeed: the claim returns a job, every `jobs` column update succeeds, the upload returns `200`, the refresh returns `202`, and with organization A context the superuser still reads 9 campaigns from 3 organizations |

### Audit leads

The leads were formulated before the audit and tested against evidence.

| # | Lead | Verdict | Evidence |
|---|---|---|---|
| L1 | API and Worker connect as the same `postgres` superuser | **Confirmed** | `docker-compose.yml:42,64`; live: `postgres` is `rolsuper`, `rolbypassrls` |
| L2 | CI tests and migrations connect as `postgres` | **Confirmed** | `ci.yml:33-35,61,66` |
| L3 | The CI integration job runs Alembic from the API container | **Confirmed** | `ci.yml:109` → `docker-compose.yml:42` |
| L4 | The test default URL uses `postgres`; no test exercises grants or RLS | **Confirmed** | `tests/conftest.py:23-27,31-35`; no `SET ROLE` or bundle usage in `tests/` |
| L5 | `0007` roles are `NOLOGIN`; nothing creates a runtime `LOGIN` role | **Confirmed** | `0007:47-68`; repository-wide search; live: only `postgres` can log in |
| L6 | Superuser and owner sessions bypass RLS; no table forces RLS | **Confirmed** | `relforcerowsecurity` false on all 14 tables; owner and control probes |
| L7 | `worker_role` can update only `(model_run_id, status)` on `jobs`, yet the Worker writes the retry and claim columns | **Confirmed**, with a correction: `claimed_at` was added in `0010`, not `0011` | `0007:175`; `0010_auth_and_jobs_additions.py:26-29`; `0011_jobs_retry_timeout_error.py:101-112`; probe P2 |
| L8 | The claim query is cross-organization, never sets context, and sees 0 jobs under `worker_role` | **Confirmed** | `worker/jobs/claim.py:16-28`; probe P1 |
| L9 | The CSV upload route writes tables `backend_role` cannot write | **Confirmed**, with a refinement: the real route stops earlier, at the RLS-filtered ownership read | `connectors.py:64,77,135,152,155`; probes P3a–P3f |
| L10 | Only `upsert.py` sets organization context, so API inserts into RLS tables are rejected | **Confirmed** | `data/normalization/upsert.py:27-32` is the only `set_config`; probes P4, P7 |
| L11 | No grants exist on tables or columns created after `0007`, and no default privileges exist | **Partially confirmed**: true for tables and default privileges; columns inherit table-level grants, and only column-scoped grants miss them | §7 G2–G4 |
| L12 | `env.py` prints the database URL including the password | **Confirmed** | `alembic/env.py:39` before this change; live migration log |
| L13 | Compose forwards `JWT_SECRET` to the Worker and never passes `CONNECTOR_TOKEN_ENCRYPTION_KEY` to the API | **Confirmed** for Compose; the API's need for the key is prospective, because no API route loads it today | `docker-compose.yml:41-45,63-66`; `connectors/oauth/crypto.py:39-62`; INT-01 §2.7 |
| L14 | INT-01 §2.2 says "SQLAlchemy async"; the repository is synchronous | **Confirmed** | INT-01 v1.1 §2.2 p.5; `db/session.py:6-7,40-51` |
| L15 | AI-07 and QA-05 assume runtime roles exist, yet no card builds them | **Confirmed** | AI-07 Entry Contract; QA-05 Definition of Done; search of all cards and the board CSV |

## 14. Known Limitations

- **Decision status:** ADR 0001 is `Proposed`. Its conditional cells depend on ARCH-02 to ARCH-05,
  which are open.
- **Probe scope:** probes model the `0007` bundles as written. They do not test a proposed grant
  set, because none is implemented.
- **Upload probe path:** the real upload route stops at the RLS-filtered ownership read. Denials at
  the Data-owned writes were shown with the exact SQL and a direct call to
  `normalize_and_upsert_batch()`.
- **Worker context:** the Worker probe with organization context (P2a) used a context set by the
  probe. How the Worker sets context per job is ARCH-05's design.
- **Environment:** the audit and probes ran locally on Windows against PostgreSQL 18.6, not in CI.
  `mypy` ran with SQLAlchemy 2.0.53. CI may resolve a different SQLAlchemy version (TRK-06 D-14).
- **Skipped tests:** pytest skipped the 9 real-PostgreSQL tests gated on `TEST_DATABASE_URL`, to
  match CI.
- **INT-01 citations:** INT-01 v1.1 pages 1–11 are images without a text layer. Citations use
  section and page numbers.
- **Unverified items:** whether the W2 joint interface review took place.
- **Board freshness:** board facts are as of the 4 October 2026 export.
- **No unit test** covers the `env.py` change (§12).

## 15. Follow-Up Tasks

All owners and suggested homes are proposals pending project-lead confirmation. Details, reviewers,
affected files and the phased sequence are in
[ADR 0001 §9](../adr/0001-runtime-boundaries-and-database-roles.md#9-follow-ups) and its Rollout
Order.

- `FU-01` — Youssef Halawa — Worker `UPDATE` on `jobs.claimed_at`, `retry_count`, `next_retry_at` —
  new card "Enable least-privilege runtime logins".
- `FU-02` — `worker_role`-scoped cross-organization visibility on `jobs` (requirement R2):
  - policy: Youssef Halawa, new card;
  - per-job context: El-Farouk Omar, WORK-03 or WORK-04, whichever first changes job execution
    (WORK-03, due 15 October 2026, is earliest).
- `FU-03` — Youssef Halawa — default privileges for future tables — new card.
- `FU-04` — Youssef Halawa — reconcile the `0007` over-grants with INT-01 §3 — new card. Removing
  `worker_role` `SELECT` on `users` and `organizations` also supports AI-07.
- `FU-05` — Ahmed Ibrahem or El-Farouk Omar (project lead's call) — per-transaction organization
  context in the API (requirement R1) — API-02, extending API-01's session and organization scoping.
- `FU-06` — Youssef Halawa (Compose and CI reviewed by El-Farouk Omar) — per-process database
  identities — new card.
- `FU-07` — secret distribution:
  - `JWT_SECRET` removal from the Worker: new card, Phase 1;
  - `CONNECTOR_TOKEN_ENCRYPTION_KEY` to the API: API-03, when OAuth token storage lands; independent
    of the runtime-login rollout.
- `FU-08` — delivered with FU-05 (API-02) — fail closed when `DATABASE_URL` is unset.
- `FU-09` — Mohamed Hassan (QA-05); Hussein Elhaddad (AI-07) — tests that connect as runtime logins;
  the role-scoped fixture can be prepared under QA-00's integration environment.
- `FU-10` — Mohamed Hassan — one INT-01 v1.2 (or within DOC-01) after all six ARCH decisions land.
- `FU-11` — El-Farouk Omar — housekeeping: remove the unused legacy root skeleton.
- Plan gap — project lead — confirm the new card "Enable least-privilege runtime logins"
  (ADR 0001 §10).

**Rollout:**

- **Phase 1** (safe at any time under the superuser runtime): FU-01 to FU-05, FU-08, and the
  `JWT_SECRET` part of FU-07.
- **Phase 2** (switch-on, last): FU-06 only, before QA-05 (12 November 2026). If it lands after
  AI-07 (5 November 2026), AI-07 uses the FU-09 fallback.
- **Independent:** the encryption-key part of FU-07 goes with API-03.
- **Fallback:** FU-09 proves grants and RLS in tests if Phase 2 slips.

## 16. References and Evidence

- **Notion task:** ARCH-01 — Reconcile Runtime Boundaries and Database Roles (export
  `ARCH-01 — Reconcile Runtime Boundaries and Databas 3e57de83a91b81f8a737c7ecd0fbf9f7.md`, 4 October
  2026).
- **Notion cards:** ARCH-02 to ARCH-06, AI-07, QA-05, QA-00, ING-01, WORK-03, WORK-04, DATA-01 and
  API-01, and the board CSV `📋 Tasks 4a4575b6b6864820924c930cbc9bb116_all.csv` (same export).
- **Pull request:** opened from branch `docs/arch-01-runtime-boundaries-db-roles`; linked from the
  Notion card.
- **Canonical contracts:** INT-01 Canonical MVP Contract Pack v1.1 (§1.1 p.2, §1.4 p.4, §2.2 p.5,
  §2.3 p.6, §2.7 p.7, §3 p.8, §6 p.12).
- **ADRs:** [ADR 0001 — Runtime Boundaries and Database Roles](../adr/0001-runtime-boundaries-and-database-roles.md)
  (`Proposed`).
- **Related technical documentation:**
  [TRK-06 integrated baseline register](../testing/TRK-06-integrated-baseline-register.md)
  (D-01, D-14, D-15, D-16, D-24, D-26); `README.md` architecture section; root, `docs/` and
  `apps/backend/` `AGENTS.md`.
- **Repository:** `main` at `e5806de5e562a1b11076ae73c026214dcc2d83c3`.
- **Test or CI evidence:** commands and results in §13. Probe scripts, raw audit dumps and logs are
  retained by the task owner and not committed, per root `AGENTS.md` "Temporary Files". CI results
  are recorded in the pull request.
- **PostgreSQL 18 documentation:**
  [Row Security Policies](https://www.postgresql.org/docs/18/ddl-rowsecurity.html);
  [`set_config`](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADMIN-SET).
