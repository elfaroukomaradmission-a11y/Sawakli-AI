# ADR 0001 — Runtime Boundaries and Database Roles

## 1. Status

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date | 4 October 2026 |
| Task | ARCH-01 — Reconcile Runtime Boundaries and Database Roles |
| Proposer | Mohamed Hassan (System QA) |
| Proposed reviewers | Hussein Elhaddad (project lead); El-Farouk Omar (Compose, CI and Worker) |
| Acknowledgers | Ahmed Ibrahem (Backend: API rows; `0007` grant rows as DATA-01 and `0007` author); Youssef Halawa (Connector & Data, including the database: Data, Connector and database rows); Abdulrahman Ehab (Frontend: Web row) |
| Acceptance | At the weekly team review. The status changes to `Accepted` only after that review. |
| Supersedes | None |

Supporting audit evidence is recorded in the
[ARCH-01 task document](../architecture/ARCH-01-runtime-boundaries-and-database-roles.md). That
document is the evidence record; this ADR is the decision record.

## 2. Context

**Runtime topology.** Sawakli AI is a modular monolith with four runtime services: Next.js Web,
FastAPI API, Python Worker and PostgreSQL. AI, Connector and Data are in-process Python modules, not
deployed services. API and Worker are built from the same backend image with different entry
commands (`README.md:56-59`).

**The `0007` design.** Migration `0007_security_roles_grants_rls` creates six `NOLOGIN` roles —
`backend_role`, `data_layer_role`, `ai_layer_role`, `connector_role`, `worker_role` and
`readonly_role` — described as mapping "1:1 to the six layers" with each service connecting "with
its own role credentials" (`0007_security_roles_grants_rls.py:44-45`). It grants table and column
privileges per role, enables row-level security (RLS) on 14 organization-scoped tables, and adds
fail-closed policies keyed on the transaction setting `app.current_org_id`.

**Today's runtime.** No process uses those roles. Every database-connected process connects as the
bootstrap superuser:

| Process | Database user | Configured at |
|---|---|---|
| API | `postgres` (superuser, `BYPASSRLS`) | `docker-compose.yml:42`; fallback `db/session.py:34-37` |
| Worker | `postgres` | `docker-compose.yml:64` |
| Migrations (CI integration job) | `postgres`, through the API container | `ci.yml:109` |
| Migrations and tests (CI backend job) | `postgres` | `ci.yml:61,66` |
| Tests (local default) | `postgres` | `tests/conftest.py:23-27` |
| Web | none | `docker-compose.yml:78-96` |

No `LOGIN` role other than the bootstrap superuser exists in the repository or in a freshly
migrated database. Because superusers and table owners bypass RLS, and no table uses
`FORCE ROW LEVEL SECURITY`, the grants and policies in `0007` are currently inert. A live probe on a
throwaway database confirmed this: with the organization context set to one organization, the
superuser still read campaigns from three organizations. With the `0007` bundles applied to
non-superuser logins, the same code paths fail in specific ways (task document §13).

## 3. Decision Drivers

- **Organization isolation is a hard invariant** (root `AGENTS.md`; INT-01 v1.1 §3 hard rule, p.8).
  Defence in depth requires the database to enforce it when application code is wrong.
- **Least privilege for runtime processes** is the second item of the ARCH-01 Definition of Done.
- **Modules share processes.** Connector, Data and AI code runs inside the API or Worker process,
  on that process's connection pool and inside its transactions.
- **Ownership is already decided.** INT-01 v1.1 §1 and §3 settle the logical owner of every table.
  This decision does not re-decide ownership.
- **Downstream tasks assume runtime roles exist.** AI-07's Entry Contract cites "DATA-01 runtime
  roles", and QA-05's Definition of Done states "Secret tables are inaccessible to unauthorized
  layers."
- **Reuse over invention.** The `0007` bundles already encode INT-01 §3 table by table.
- **Neighbouring decisions are open.** ARCH-02 to ARCH-05 decide where ingestion, AI execution and
  provider access run, which determines some bundle memberships.

## 4. Options Considered

| Option | Description | Outcome |
|---|---|---|
| **(a) Per-process logins inheriting bundles** | One runtime login each for API and Worker, `LOGIN NOSUPERUSER NOBYPASSRLS`, inheriting the `0007` bundles their process needs. A separate migration identity owns the schema. | **Chosen.** Enforceable by PostgreSQL, reuses `0007`, matches the real process boundary. |
| (b) Keep one superuser | Accept the current single identity and rely on application code. | Rejected. Grants and RLS stay inert, `connector_tokens` stays readable by every process, and the premises of AI-07 and QA-05 cannot be met. |
| (c) One login per module | Give Backend, Data, AI and Connector code their own logins. | Rejected as not possible in-process. A single request crosses modules in one transaction (the CSV upload route, `api/routes/connectors.py:92-182`, calls Connector parsing and Data upserts). Separate logins would need separate connections and would break that transactional atomicity. |

## 5. Decision

### D1 — Database identity is per runtime process, not per module

- **Runtime processes.** The runtime has four services: Web, API, Worker and PostgreSQL. AI,
  Connector and Data are in-process modules.
- **Web** holds no database credentials. This matches the current Compose file
  (`docker-compose.yml:78-96`) and INT-01 §3 ("UI never queries any DB table directly").
- **Migration identity.** The database owner runs Alembic only and is never used by API or Worker
  at runtime. In local development and CI it may remain the bootstrap superuser.
- **API runtime login** and **Worker runtime login** are each `LOGIN NOSUPERUSER NOBYPASSRLS`.
- **Bundles.** The six `0007` roles are kept as `NOLOGIN` permission bundles. Runtime logins inherit
  bundles by membership.
- **Conditional cells.** Where a neighbouring ARCH task has not decided yet, the bundle cell is
  marked `Conditional — ARCH-0x` and no answer is chosen here.
- **Accepted limitation.** Module-level separation inside one process cannot be enforced by
  PostgreSQL. Example: Connector-only access to `connector_tokens` while Connector code runs inside
  the API process. Inside a process, that separation is enforced by code ownership, contracts and
  tests (AI-07, QA-05).

### D2 — Row-level security stays, fail-closed, as defence in depth

RLS becomes active only once the runtime logins exist. It creates the following runtime
**requirements**. This ADR records them as requirements only; it does not implement them.

| Requirement | Statement | Implementation owner |
|---|---|---|
| **R1 — API organization context** | For every authenticated request, the API sets `app.current_org_id` transaction-locally (`set_config(..., true)`, the existing pattern in `data/normalization/upsert.py:27-32`) before any organization-scoped statement. Because a transaction-local setting ends at `COMMIT` or `ROLLBACK`, the context must be **re-applied for every transaction** of the request, including after each commit and rollback. | ARCH-02 (API side) |
| **R2 — Worker cross-organization visibility** | The Worker needs **role-scoped cross-organization visibility on `jobs`** for the bundle `worker_role`, covering the claim query (`worker/jobs/claim.py:9-28`), the running-job scan (`worker/scheduler/loop.py:50-60`) and the timeout scan (`worker/scheduler/loop.py:77-103`). After a job is claimed, the Worker sets the organization context for that job's organization-scoped work. | ARCH-05 (Worker side) |

R1 is required because routes commit and then continue: `api/routes/analysis.py:88-100` commits a
new job and then refreshes it in a new transaction. A probe that set the context once per request
committed the job and then failed the refresh. The same route returned `202 Accepted` when the
context was re-applied on every transaction.

### Intended Per-Process Matrix

**Bundle membership**

| Process | `backend_role` | `data_layer_role` | `ai_layer_role` | `connector_role` | `worker_role` | `readonly_role` |
|---|---|---|---|---|---|---|
| API runtime | Required now | Conditional — ARCH-02, ARCH-04 | Not granted | Conditional — ARCH-04 | Not granted | Not granted |
| Worker runtime | Not granted | Conditional — ARCH-04, ARCH-05 | Conditional — ARCH-03, ARCH-05 | Conditional — ARCH-04, ARCH-05 | Required now | Not granted |
| Migration identity | Not applicable — schema owner | Not applicable | Not applicable | Not applicable | Not applicable | Not applicable |
| Web | Not applicable — no database credentials | Not applicable | Not applicable | Not applicable | Not applicable | Not applicable |

**Conditions**

- **API `data_layer_role`:** needed only if CSV ingestion stays in-process in the API (ARCH-02
  transaction boundary; ARCH-04 Connector-to-Data handoff).
- **API `connector_role`:** needed only if OAuth token storage runs in the API process (INT-01 §2.7
  `store_oauth_token`; ARCH-04 credentials).
- **Worker `ai_layer_role`:** needed only if AI-06 runs inside the Worker (ARCH-03, ARCH-05).
- **Worker `data_layer_role` and `connector_role`:** needed only for WORK-03 recurring sync
  (ARCH-04, ARCH-05).

**Effective privilege per INT-01 §3 table group**

Logical owners are unchanged from INT-01 v1.1 §3 (p.8). Each cell shows the privilege inherited
from the bundles marked `Required now`, then any conditional addition.

| Table group (logical owner) | API runtime | Worker runtime |
|---|---|---|
| `users`, `organizations`, `organization_members`, `oauth_connections`, `jobs`, `execution_logs` (Backend) | Required now: `SELECT`, `INSERT`, `UPDATE`, `DELETE` via `backend_role`. RLS applies to `jobs`, `execution_logs` and `oauth_connections` (R1). | Required now: `jobs` `SELECT` and `UPDATE (status, model_run_id)` via `worker_role`. The Worker also writes `claimed_at`, `retry_count` and `next_retry_at` (grant drift; §8). `organizations` and `users` `SELECT` via `worker_role` (see boundary delta B5). |
| `data_sources` (Backend creation / Data status fields) | Required now: `SELECT`, `INSERT`. Status-column `UPDATE`: Conditional — ARCH-04. | Required now: `SELECT`. Status-column `UPDATE`: Conditional — ARCH-04, ARCH-05. |
| `connector_tokens` (Connector exclusively) | Not granted. Conditional — ARCH-04. | Not granted. Conditional — ARCH-04, ARCH-05. |
| `raw_api_responses` (Data) | `SELECT` via `backend_role` (over-grant; §8). Write: Conditional — ARCH-02, ARCH-04. | Conditional — ARCH-04, ARCH-05. |
| `campaigns`, `ad_groups`, `ads`, `creatives`, `daily_metrics`, `ga_events`, `feature_daily` (Data) | Required now: `SELECT`. Write: Conditional — ARCH-02, ARCH-04. | Read: Conditional — ARCH-03, ARCH-05. Write: Conditional — ARCH-04, ARCH-05. |
| `model_runs`, `forecasts`, `anomalies`, `recommendations`, `action_simulations` (AI) | Required now: `SELECT`, and `UPDATE (status)` on `recommendations`. | Required now: `model_runs` `SELECT`, `INSERT`. Other AI output writes: Conditional — ARCH-03, ARCH-05. |

## 6. Consequences

**Positive**

- PostgreSQL enforces process-level least privilege and organization isolation as defence in depth,
  independent of application filters.
- `connector_tokens` becomes unreadable to any process that does not hold `connector_role`.
- Migration identity is separated from runtime identity, so a compromised runtime process cannot
  alter the schema.

**Negative and required work**

- **Runtime logins must not be enabled before the blocking follow-ups land.** Against the `0007`
  bundles as written, the current code fails in these ways:
  - the Worker claims no jobs;
  - the Worker cannot write `claimed_at`, `retry_count` or `next_retry_at`;
  - the API cannot create jobs or data sources without organization context;
  - the CSV upload path cannot write Data-owned tables.

  These are follow-ups FU-01, FU-02 and FU-05, and the ARCH-02 and ARCH-04 decisions.
- **Fail-closed reads look like empty results, not errors.** Under RLS without organization
  context, list endpoints return empty lists and owned resources return `404 Not Found`. Tests must
  therefore assert positive visibility of the caller's own rows, not only the absence of other
  organizations' rows.
- **Configuration grows.** Compose, CI and environment files must carry distinct runtime and
  migration credentials.

**Accepted limitation**

- Inside the API or Worker process, every in-process module shares that process's login. The
  database cannot distinguish Backend code from Connector or Data code in the same process. INT-01
  §3 "Explicitly Forbidden" cells between co-located modules are enforced by code ownership,
  contracts and tests (AI-07, QA-05), not by PostgreSQL.

**Lifecycle**

- D1 and D2 are `Proposed`. No runtime login, grant, policy, Compose or CI change is implemented by
  this decision.

## 7. Boundary Delta vs INT-01 v1.1

Only passages that change or need clarification are listed. Logical table ownership in INT-01 §1
and §3 is unchanged.

| # | INT-01 v1.1 passage | v1.1 says | Delta |
|---|---|---|---|
| B1 | §3 Ownership & Access Matrix (p.8) | Owners and readers per logical layer | **Clarification:** add a runtime-process view. Web, API, Worker and the migration identity are the database principals. Layers map to processes as in §5 of this ADR. |
| B2 | §3 "Explicitly Forbidden" column (p.8); §1.4 (p.4) | Connector owns `connector_tokens` exclusively; other layers are forbidden | **Clarification:** between modules in the same process, the prohibition is enforced by code ownership, contracts and tests, not by PostgreSQL (D1 accepted limitation). |
| B3 | §3 hard rule (p.8) | No query on campaign, metric or AI-output data runs without an `organization_id` filter | **Addition:** RLS is defence in depth behind the hard rule, with runtime requirements R1 and R2. The application filter remains mandatory. |
| B4 | §2.2 Backend ↔ Database (p.5) | "Direct SQLAlchemy async reads/writes" | **Change:** the implementation uses synchronous SQLAlchemy `Session` (`db/session.py:6-7,40-51`). |
| B5 | §1.1 Backend / Auth-Owned Tables (p.2) | "Only Backend queries them directly" | **Clarification needed:** `0007` grants `worker_role` `SELECT` on `users` and `organizations`, and no current Worker code reads them. Whether the Worker scheduler reads `organizations` (INT-01 §2.3 nightly batch "one job per active org") is ARCH-05's decision. |
| B6 | New statement | — | **Addition:** a migration identity owns the schema and is never a runtime identity. Web holds no database credentials. |

The legacy root directories `agent/`, `api/`, `connector/`, `database/`, `ui/` and `worker/` are not
part of any runtime boundary (`README.md:89-92`; TRK-06 register D-26). They are recorded here and
proposed for removal as a follow-up (FU-11). Nothing is deleted by this decision.

## 8. Fixture/Contract Delta

None of these changes is made in the pull request that introduces this ADR.

| Item | Required change | Proposed owner | Timing |
|---|---|---|---|
| INT-01 v1.1 §2.2, §3 (and §1.1 once ARCH-05 decides) | Apply boundary delta B1–B6 in INT-01 v1.2 | Mohamed Hassan (contract owner) | After all six ARCH decisions land, as one v1.2 or within DOC-01 |
| Successor migration to `0007` | Add Worker `UPDATE` on `jobs.claimed_at`, `retry_count`, `next_retry_at`; add a `worker_role`-scoped policy on `jobs` (R2); add default privileges for future tables; reconcile the `0007` over-grants listed below. Historical migrations stay unchanged. | Youssef Halawa, reviewer Ahmed Ibrahem — pending project-lead confirmation | After acceptance |
| `docker-compose.yml:42,64`; `ci.yml:61,66,109`; `.env.example:9-13` | Split `DATABASE_URL` into API runtime, Worker runtime and migration connection strings of the form `postgresql+psycopg://<user>:<password>@<host>/<db>`. Run CI migrations as the migration identity, not through the API's runtime URL. | El-Farouk Omar — pending project-lead confirmation | After the successor migration |
| Test fixtures: `tests/conftest.py:23-35`, `tests/test_org_isolation.py`, `tests/integration/connectors/oauth/test_postgres_repository.py` | Connect as runtime logins where isolation or secret-table access is asserted. Superuser connections cannot prove grants or RLS. | Mohamed Hassan (QA-00, QA-05); Hussein Elhaddad (AI-07) — pending project-lead confirmation | With QA-00, AI-07, QA-05 |
| `README.md:39` (Database row) | Update after runtime logins are implemented | Implementing pull request | After implementation |
| `tests/contracts/` | No change required; the contract fixtures contain no role or grant definitions | — | — |

**`0007` over-grants to reconcile** (drift, not separate defects):

- `backend_role` `SELECT` on `raw_api_responses`. INT-01 §3 keeps reads internal to Data, and no
  Backend code reads the table.
- `backend_role` `UPDATE` and `DELETE` on `execution_logs`. INT-01 §1.1 defines it as append-only.
- `backend_role` full privileges on `users` and `organizations`. INT-01 §2.2 says "registration
  only".
- `ai_layer_role` `UPDATE` and `DELETE` on AI output tables. INT-01 §3 says INSERT-only, while §1.3
  assigns `model_runs` status updates to the AI pipeline; ARCH-03 input is required.
- `worker_role` `SELECT` on `users` and `organizations` (B5).

## 9. Follow-Ups

Every owner, reviewer and suggested home below is a **proposal pending project-lead
confirmation**. None is assigned by this ADR.

| ID | Follow-up | Proposed owner | Proposed reviewer | Affected file or contract | Blocks | Suggested home (proposal) |
|---|---|---|---|---|---|---|
| FU-01 | `worker_role` cannot update `jobs.claimed_at` (added in `0010`), `retry_count` or `next_retry_at` (added in `0011_jobs_retry_timeout_error`), which the Worker writes | Youssef Halawa | Ahmed Ibrahem | `0007` successor migration; `worker/scheduler/loop.py:23,31,130` | Runtime-login rollout; QA-05 | New card "Enable least-privilege runtime logins" (§10) |
| FU-02 | The Worker scans `jobs` across organizations, but every policy is `TO public`, so under RLS it sees no jobs (R2) | Policy: Youssef Halawa. Per-job context: El-Farouk Omar (ARCH-05) | Ahmed Ibrahem | `0007` successor migration; `worker/jobs/claim.py:9-28`; `worker/scheduler/loop.py:50-60,77-103` | WORK-03, WORK-04 under runtime logins; QA-05 | Policy: new card (§10). Per-job context: WORK-03 or WORK-04, whichever first changes job execution (WORK-03, due 15 October 2026, is earliest), because WORK-03 sync is planned organization-scoped work in the Worker. |
| FU-03 | No default privileges exist, so tables created by future migrations receive no bundle grants | Youssef Halawa | Ahmed Ibrahem | `0007` successor migration | Every future table under runtime logins | New card (§10) |
| FU-04 | Reconcile the `0007` over-grants with INT-01 §3 (§8 list). Removing `worker_role` `SELECT` on `users` and `organizations` also supports AI-07 ("AI cannot access users/OAuth secrets"), because AI code running inside the Worker shares the Worker login. | Youssef Halawa | Ahmed Ibrahem; ARCH-03 input for AI output grants | `0007` successor migration; INT-01 §3 | AI-07 (for the `users` read) | New card (§10) |
| FU-05 | The API sets no organization context per transaction (R1), so RLS rejects job and data-source creation and reads return empty results | Project lead to choose: Ahmed Ibrahem (ARCH-02) or El-Farouk Omar (API-01 session and organization scoping) | Hussein Elhaddad | `api/deps.py`; `db/session.py:54-59`; `api/routes/analysis.py`, `jobs.py`, `connectors.py` | AI-07; QA-05; runtime-login rollout | API-02. The organization-context hook extends API-01's session and organization scoping. |
| FU-06 | API, Worker and migrations share one superuser identity in Compose and CI | Youssef Halawa | El-Farouk Omar (Compose and CI) | `docker-compose.yml:42,64`; `ci.yml:61,66,109`; `.env.example:9-13` | QA-05 | New card (§10) |
| FU-07 | Compose forwards `JWT_SECRET` to the Worker, which does not use it. It also passes `CONNECTOR_TOKEN_ENCRYPTION_KEY` to no process, though OAuth token storage will need the key where Connector code runs. | `JWT_SECRET` removal: Youssef Halawa. Encryption key: Ahmed Ibrahem (API-03), with ARCH-04 | `JWT_SECRET`: El-Farouk Omar. Encryption key: Youssef Halawa | `docker-compose.yml:41-45,63-66`; `connectors/oauth/crypto.py:39-62` | OAuth token storage rollout | `JWT_SECRET` removal: new card (§10), Phase 1. Encryption key to the API: API-03, where the OAuth callback lives, when OAuth token storage lands; independent of the runtime-login rollout. |
| FU-08 | The runtime falls back to a hard-coded superuser connection string when `DATABASE_URL` is unset, instead of failing | Delivered with FU-05 (same owner) | Hussein Elhaddad | `db/session.py:34-37` | Least-privilege rollout | Delivered with FU-05 (API-02) |
| FU-09 | Tests connect as the superuser and cannot prove grants or RLS | Mohamed Hassan (QA-05); Hussein Elhaddad (AI-07) | Hussein Elhaddad; Mohamed Hassan | `tests/conftest.py:23-35`; `tests/test_org_isolation.py`; `tests/integration/connectors/oauth/test_postgres_repository.py` | AI-07; QA-05 | QA-05 and AI-07. The role-scoped test fixture can be prepared under QA-00's integration environment. |
| FU-10 | Apply boundary delta B1–B6 to INT-01 | Mohamed Hassan (contract owner) | Hussein Elhaddad | INT-01 v1.1 §1.1, §2.2, §3 | — | After all six ARCH decisions land: one INT-01 v1.2 (or within DOC-01), not immediately after this ADR |
| FU-11 | Remove the unused legacy root skeleton | El-Farouk Omar (repository administrator) | Hussein Elhaddad | `agent/`, `api/`, `connector/`, `database/`, `ui/`, `worker/` | — | El-Farouk Omar housekeeping. The documentation-governance check lists only added, copied, modified and renamed files (`--diff-filter=ACMR`), so a deletion-only pull request passes it. If the pull request also adds or modifies a file under an implementation path, it needs a task document or the `documentation-exempt` label. |

The CSV upload path in the API writes Data-owned tables and `data_sources` status columns. That
existing item is tracked by TRK-06 D-24 under ARCH-02, ARCH-04, ING-01 and API-03 and is not
duplicated here. Its privilege consequence is the conditional API `data_layer_role` cell in §5.

### Rollout Order

| Phase | Contents | Condition |
|---|---|---|
| **Phase 1 — preparation** | The grants migration (FU-01, the policy part of FU-02, FU-03, FU-04); the API per-transaction organization context (FU-05 with FU-08); the Worker per-job context (the context part of FU-02); `JWT_SECRET` removal from the Worker (FU-07 part) | Safe to merge at any time, because the superuser runtime ignores grants and RLS and the Worker does not read `JWT_SECRET` |
| **Phase 2 — switch-on, last** | Runtime logins and the Compose/CI split (FU-06) | Only after Phase 1 has merged and the conditional bundles are decided (ARCH-02 to ARCH-05). Target: before QA-05 (due 12 November 2026). If it lands after AI-07 (due 5 November 2026), AI-07 uses the fallback. |
| **Fallback** | Runtime logins created in the test database (FU-09) | If Phase 2 slips, QA-05 and AI-07 can still prove database-level grants and RLS in tests, independent of Compose |
| **Independent** | `CONNECTOR_TOKEN_ENCRYPTION_KEY` to the API (FU-07 part) | With API-03 whenever OAuth token storage lands; not part of the runtime-login rollout |

## 10. Plan Gap

No task card in the 4 October 2026 board export builds the runtime logins, a successor grants
migration, the Compose and CI credential split, or request-scoped organization context code.
Downstream tasks nevertheless depend on that work:

- AI-07 Entry Contract: "DATA-01 runtime roles plus AI-06 interface".
- QA-05 Definition of Done: "Secret tables are inaccessible to unauthorized layers."

DATA-01 (Done) delivered the `NOLOGIN` bundles only. The project lead is asked to assign this work.

**Suggested home (proposal, pending project-lead confirmation):** one new card, "Enable
least-privilege runtime logins".

- **Proposed owner:** Youssef Halawa, with the Compose and CI part reviewed by El-Farouk Omar.
- **Covers:** FU-01, the policy part of FU-02, FU-03, FU-04, FU-06, and the `JWT_SECRET` part of
  FU-07.
- **Existing cards:** FU-05 and FU-08 go to API-02. The per-job context part of FU-02 goes to
  WORK-03 or WORK-04, whichever first changes job execution. The encryption-key part of FU-07 goes
  to API-03.
- **Sequencing:** follows the phases in §9 Rollout Order.

## 11. Related Decisions

| Decision | Owner | What this ADR needs from it |
|---|---|---|
| ARCH-02 — Backend Transaction and API Contract Deltas | Ahmed Ibrahem | Whether CSV ingestion stays in-process in the API (API `data_layer_role`); the transaction boundary that satisfies R1; migration coordination and schema reviewer for the successor migration |
| ARCH-03 — AI Pipeline and Persistence Interfaces | Hussein Elhaddad | Whether AI-06 runs in the Worker (Worker `ai_layer_role`); AI output write privileges (INSERT-only vs `model_runs` status update); whether AI reads `feature_daily` or `daily_metrics` |
| ARCH-04 — Connector-to-Data Handoff Contracts | Youssef Halawa | Who persists `RawResponse` and writes `data_sources` status (`data_layer_role` placement); where provider credentials and the token encryption key live (`connector_role` placement) |
| ARCH-05 — Worker Dispatch and Recovery Boundaries | El-Farouk Omar | How the Worker sets organization context per job (R2); whether the scheduler reads `organizations`; which bundles WORK-03 sync needs |
| ARCH-06 — Frontend API Client and State Conventions | Abdulrahman Ehab | No database input. Acknowledgement of the Web row (no database credentials). |

## 12. References

- **Notion task:** ARCH-01 — Reconcile Runtime Boundaries and Database Roles (board export of
  4 October 2026).
- **Notion cards cited:** ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06, AI-07, QA-05, QA-00, DATA-01,
  ING-01, WORK-03, WORK-04, API-01 (same export).
- **Canonical contract:** INT-01 Canonical MVP Contract Pack v1.1 (2 October 2026): §1.1 p.2, §1.4
  p.4, §2.2 p.5, §2.3 p.6, §2.7 p.7, §3 p.8, §6 p.12.
- **Evidence record:**
  [ARCH-01 task document](../architecture/ARCH-01-runtime-boundaries-and-database-roles.md) —
  inventory, live audit, probes and verification.
- **Baseline:** [TRK-06 integrated baseline register](../testing/TRK-06-integrated-baseline-register.md)
  (D-15, D-16, D-24, D-26).
- **Repository:** `main` at `e5806de5e562a1b11076ae73c026214dcc2d83c3`;
  `apps/backend/alembic/versions/0007_security_roles_grants_rls.py`, `0010_auth_and_jobs_additions.py`,
  `0011_jobs_retry_timeout_error.py`; `docker-compose.yml`; `.github/workflows/ci.yml`.
- **PostgreSQL 18 documentation:** [Row Security Policies](https://www.postgresql.org/docs/18/ddl-rowsecurity.html);
  [`set_config`](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADMIN-SET).
