# TRK-06 — Review Integrated Baseline and Present Evidence Register

<!--
Audit record, not an implementation. Status labels: checks use PASS / FAIL / NOT RUN — <reason>;
acceptance items use Met / Not yet / At risk; claims use Confirmed / Partly confirmed / Refuted / Unverified.
-->

## 1. Overview

TRK-06 measures what the Sawakli AI repository actually contains against what the task board claims. It covers `main` plus the three open pull requests (#16, #18, #19), evaluated alone and merged together. It is an audit: no production code was changed, and nothing here was merged or pushed except this document.

The register answers three questions from the TRK-06 card's Definition of Done:

1. What exactly are `main` and the open PR heads, how far have they been reviewed, and is each task's acceptance case covered?
2. Do the real contract validators work, where are placeholders, and what is missing from CI?
3. What does the combined baseline look like, what does one negative test path show, and what should reviewers decide?

Snapshot: **2026-09-29 13:56 UTC**. `main` = `b4df966`. Board state = Notion Tasks export of 29 Sep 2026, 15:57 (Africa/Cairo).

**Headline findings (details and evidence in §13–§15):**

- **Gates:** `main` and the combined baseline both pass every CI gate with the dependency versions CI last used. Merging #16, #18 and #19 together introduces no new failure; one merge conflict (`apps/backend/pyproject.toml`) needs resolving.
- **Dependency drift:** with today's dependency resolution, `main` itself fails `mypy`. SQLAlchemy 2.1.0 reached PyPI on 24 Sep 2026 and 2.1.1, the version resolved here, on 25 Sep. `pyproject.toml` allows both. CI hit this on 29 Sep: this register's own PR (#20, run 36598495262) and the next `main` push run (36604830235) both failed Backend `mypy` with the same 5 errors.
- **CSV path:** the upload path does not yet work end to end. Most of the missing work is scheduled in other tasks, and one defect sits in an open PR.
  - The API-03 upload endpoint (#18) accepts and parses a valid 180-row file, which is what API-03's Definition of Done asks for. It writes **0 rows**. Saving rows is ING-01's Definition of Done (due 15 Oct), and ING-01 is one of API-03's completion gates (API-03 due 22 Oct).
  - The defect: #18 also sets `data_sources.status` to `demo_data` from the Backend. INT-01 §3 assigns that field to the Data Layer, and API-03's Entry Contract says "fix PR #18 status now".
  - The UI (#16) makes no upload request. UI-03 is scheduled to consume API-03's upload/status contract on 20 Oct.
  - The Data-layer normalization works when called directly. The production call into it, including the `raw_api_responses` writer, is ING-01's.
- **Review leads:** all 16 were checked. Leads 1–5 are the 23 Sep reconciliation notes (author not recorded on the cards). All five are **confirmed** as descriptions of the code, but not every one rests on a Definition of Done: lead 5's tenant-scoped grouping appears in no AI-02 Definition of Done, Entry Contract or completion gate, and organization-isolation tests are AI-07's Definition of Done. Of leads 6–16, 10 are confirmed (lead 16 only partly, on whether ING-01 supersedes DATA-03) and 1 is refuted: lead 13, because the `raw_api_responses` idempotency key *does* exist. §13.4 records, for each open item, whether it belongs to the task itself, waits on a dependency, or belongs to another task.
- **Contract validators:** two of the five QA-01 validators are exit-0 placeholders, the contract covers 8 of 22 tables, and no CI job runs any of them.

## 2. Scope

### In Scope

- Heads, review state and CI state of `main` and PRs #1–#19 (#16, #18, #19 open; #17 closed).
- All CI gates from `.github/workflows/ci.yml` on `main` and on a local combined branch (`main` + #16 + #18 + #19), plus the documentation-governance script per PR.
- The five contract validators under `tests/contracts/` and the deliberate-mismatch negative test.
- Placeholder tests, placeholder packages and CI wiring gaps.
- A normal, failure, contrast and UI trace through the CSV upload path against real PostgreSQL.
- A task-to-commit register for 24 tasks, plus ING-01 and QA-00.
- Verification of the 16 review leads, of which leads 1–5 are the 23 Sep reconciliation notes (author not recorded on the cards).
- Draft reviewer decisions for #16, #18 and #19 (delivered to the task owner separately, not posted).

### Out of Scope

Fixing anything is out of scope; each item is mapped to its owner in §15:

- DATA-03 port
- ING-01 implementation
- migrations
- idempotency key redesign
- `feature_daily` decision
- CI validator wiring (QA-00)
- placeholder removal
- changes to other contributors' PRs

Layer-level baseline reviews belong to TRK-01 (Frontend), TRK-02 (Backend), TRK-03 (AI), TRK-04 (Connector & Data) and TRK-05 (Worker). This register cross-references them and does not replace them (see §14, overlap).

## 3. Prerequisites

Board fields quoted verbatim from the Notion export. docs/AGENTS.md prefers the term "Prerequisites", while the 2026-09 cards say "Depends On (2026-09)" is authoritative. That conflict is logged, not resolved, in §14 (D-01).

| Task / Contract | Why Required |
|---|---|
| TRK-06 card, `Depends On (2026-09)`: none ("Directional acceptance dependencies: None") | No hard task dependency |
| TRK-06 card, `Entry Contract`: "No hard prerequisite. Inspect QA-01/CI/open PRs; establish task-to-commit baseline." | Defines the inputs used below |
| INT-01 Canonical MVP Contract Pack (Notion PDF `INT-01_Canonical_MVP_Contract_Pack.pdf`, rev. 20 Aug 2026) | Reference for tables, endpoints, ownership and error shape. It is not in the repo, and `docs/contracts/` does not exist yet |
| PROD-01 Month-One Scope Freeze (Notion PDF `PROD-01_Month-One_Scope_Freeze.pdf`) | CSV template (§3) used for the upload trace; acceptance bars (§4.2) |
| `tests/contracts/canonical.json` | The only machine-readable contract in the repo |
| ADRs | None. `docs/adr/` contains only `.gitkeep` |

QA-00 lists TRK-06 as its `Depends On (2026-09)`, so this register is an input to QA-00.

## 4. Architecture

### How the baseline was built

```text
origin/main b4df966
  └─ merge pr/16 c069577  → 178fe3a   (clean)
      └─ merge pr/18 3bd89d2 → e9bbfdd   (clean; api/main.py auto-merged with #16)
          └─ merge pr/19 0ef4e41 → 79f84ba   (CONFLICT: apps/backend/pyproject.toml, resolved by union)
```

The branch `trk-06/combined-baseline` exists only locally and was never pushed. The conflict is mostly line endings: `main`'s dependency block is LF inside a mostly-CRLF file, and #18 and #19 each rewrote it as CRLF. Its only content difference is #18's added `"python-multipart>=0.0.20,<1.0"`, which was kept.

### Normal trace, as the code actually runs (combined branch)

```text
UI  /setup/organization ──register+login──▶ API /api/auth/*            (works)
UI  /setup/connector    ──(no request)──▶   —                          (CSV stays in browser state)

API POST /api/connectors/setup ─▶ INSERT data_sources(csv_demo, 'disconnected')
API POST /api/connectors/csv/{id}/upload
      ├─ org-scoped ownership check                       connectors.py:198-208
      ├─ parse_csv_upload()  (pure, no I/O)               connectors.py:218 → connectors/csv/parser.py:64
      ├─ UPDATE data_sources SET status='demo_data'       connectors.py:237-251
      └─ 200 {…, row_count, parsed_rows[all], parse_warnings}
         ✗ raw_api_responses   ✗ staging   ✗ campaigns / daily_metrics / ga_events

Data layer (exists, works, no production caller):
  staged_row_from_csv_dict()      data/staging/adapters.py:7
  normalize_and_upsert_batch()    data/normalization/pipeline.py:94 → upsert.py:220 (daily_metrics), :246 (ga_events)
```

### Ownership boundaries

According to INT-01 §3 (PDF p.8), the Data Layer owns `raw_api_responses`, `campaigns`, `daily_metrics`, `ga_events` and the status fields of `data_sources`. On the combined branch, the Backend route writes `data_sources.status` (D-24), and no layer writes `raw_api_responses` (lead 6).

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| Repository | git | Yes | `github.com/elfaroukomaradmission-a11y/Sawakli-AI`, fresh clone, `core.autocrlf=false`, `refs/pull/*/head` fetched | Code, history, migrations, tests |
| PR metadata | JSON | Yes | `gh pr view N --json state,reviewDecision,reviews,statusCheckRollup,mergeable,author,title,headRefName,…` for N = 1..19 | Heads, reviews, CI |
| Board | Notion export | Yes | `all notion tasks.zip` (29 Sep 15:57): `📋 Tasks …_all.csv` (85 rows, 38 columns) plus card `.md` files and attachments | Status, Member, Track, due dates, DoD, notes |
| Earlier single-card exports | Notion export | No | 8 zips (29 Sep 15:25–15:38) | Compared with the full export: link format differs only, no content difference |
| Contract PDFs | PDF | Yes | INT-01, PROD-01 (Notion attachments) | Reference contract |
| Test CSV | CSV | Yes | Generated to PROD-01 §3: 2 campaigns × 90 days, all 10 columns, 180 rows | Normal trace input |
| Failure inputs | CSV | Yes | 0-byte file; header `day,name,channel,cost` | Failure trace |
| Test users | synthetic | Yes | Created through `POST /api/auth/register` on a local database (no seeded user exists, D-22) | Authentication for traces. Values are kept locally and are not in this document |

No live Notion page, deployed environment or production data was used. `README.md` and `docs/README.md` list no deployed URL.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| This document | Markdown | No | Team, QA-00, reviewers | Evidence register |
| Task-to-commit register | table (§13.4) | No | Board owners | 24 tasks + ING-01 + QA-00 |
| Lead verdicts | table (§13.5) | No | Mohamed Hassan; owners of DATA-05, QA-02, UI-03, API-03 and AI-02 | 16 leads; leads 1–5 are the 23 Sep reconciliation notes (author not recorded on the cards) |
| Draft PR reviews for #16, #18, #19 | text | No | Mohamed Hassan (posts them himself) | Not part of this document. Verdicts summarized in §13.6 |
| Follow-up map | list (§15) | No | Task owners | Findings mapped to existing cards |

## 7. Rules and Semantics

- **Measure, don't grade.** The five reconciled tasks were reset to Backlog on 23 Sep with revised deadlines, so "Not yet" is an expected state. It is not a failure.
- **Check results** use exactly `PASS`, `FAIL` or `NOT RUN — <reason>` (root `AGENTS.md`, "Verification Truthfulness").
- **Board-Done acceptance** is labelled `Yes / Partial / No / Unverifiable`. "Yes (by tests)" means the task's tests pass and TRK-06 did not trace the behaviour further.
- **Reconciled-task DoD items** are labelled `Met / Not yet / At risk`. "At risk" means the item looks done but has a defect that would stop it passing review.
- **Scope of open items** (added 30 Sep after a Definition-of-Done sweep): each open item names the task whose Definition of Done, Entry Contract, completion gates or internal handoff requires it. Where it waits on another task, that task and its due date are given. "In window" means the owning task's revised deadline has not passed; an in-window item that is not yet built is not a fault. "Incorrect behaviour in PR" means submitted code already behaves against a Definition of Done line or contract clause, and it is the only basis for **Request changes** in §13.6. An expectation stated only in the 23 Sep reconciliation notes or the 24 Sep handoff notes (author not recorded on the cards) is labelled note-only.
- **Claims** are labelled `Confirmed / Partly confirmed / Refuted / Unverified`. "Unverified" always states what was tried and what would verify it.
- **Every fact carries a source:** a command and its output, a `file:line`, a commit SHA, a PR/CI URL, or a Notion export file name. `file:line` refers to the combined branch `79f84ba` unless prefixed `main:` or `pr/N:`.
- **CI-equivalent environment:** `pyproject.toml` pins ranges, not versions, so gates were run with the dependency set CI last resolved (SQLAlchemy 2.0.53), and also with today's resolution (SQLAlchemy 2.1.1) where the result differs.
- **Isolated scratch databases:** each gate run starts from freshly created `sawakli` and `sawakli_test` databases, as CI does. Traces use a separate `sawakli_trace` database.

## 8. Public Interfaces

N/A — this is an audit record, and it adds no function, endpoint, event, job or table. The interfaces exercised by the traces are listed in §4 and §11 with their `file:line`.

## 9. Data Ownership

### Reads

- Repository contents at the SHAs in §16; GitHub PR/CI metadata via `gh`; the Notion export files listed in §16.

### Writes

- Local, throwaway PostgreSQL databases only (`sawakli`, `sawakli_test`, `sawakli_trace` in a local Docker container).
- One local branch (never pushed).
- This document, which is the only file committed.

### Must Never Read

- Real credentials, tokens or `.env` files. None exist in the clone, and none were requested.

### Must Never Write

- Any Notion card, PR, review, comment or remote branch. None were written; review drafts go to the task owner for manual posting.

## 10. Security

The traces checked these security properties:

- **Organization isolation (API):** PASS for the paths traced. An upload to another org's data source returns 404 "Connector not found" (`connectors.py:106-133`, `:198-208`). An upload with no token returns 401. `get_auth_context` loads the org and membership from the JWT (`api/deps.py:38-70`).
- **Organization isolation (Data, #16):** At risk. `upsert.py:232-242` and `:256-264` overwrite `organization_id` when a `(campaign_id, date)` row already exists. No test uses two organizations (D-30).
- **Organization isolation (AI, #19):** At risk. `ai/anomaly/detector.py:71` groups by `campaign_id` only. The evaluation test gives every record a random `organization_id` (`tests/unit/ai/test_detector_evaluation.py:16`) and still passes. No AI-02 Definition of Done line asks for tenant grouping; the 23 Sep reconciliation notes and the 24 Sep handoff note do (note-only). Organization-isolation tests are AI-07's Definition of Done (due 5 Nov), and tenant-scoped input contracts are ARCH-03's (due 8 Oct). Root `AGENTS.md` ("Add cross-tenant tests whenever a changed data path could cross this boundary") still applies to #19.
- **Token exposure (API-03):** PASS for the responses observed. No token field appears in any response, and 422 bodies withhold the developer message (`connectors.py:225`).
- **Secrets in logs:** a finding. `apps/backend/alembic/env.py:39` prints the full database URL, including the password, on every Alembic run (D-16).
- **Frontend:** `apps/web/src/lib/mock-auth.ts:51-65` defines a hard-coded demo session, used by the login page's "Open demo workspace" (`login/page.tsx:38-41`). `middleware.ts:9` only checks that a cookie exists. The backend still requires a JWT, so no server data is exposed. On `main`, `auth.service.ts` accepted a hard-coded demo credential pair (`main:apps/web/src/services/auth.service.ts:4-20`); #16 replaces this with real API calls.
- **This audit's own handling:** only synthetic test users on local databases. JWTs were redacted from saved trace output. No credential appears in this document.

## 11. Error and Edge-Case Behavior

Observed on the combined branch through the real API against PostgreSQL 18.6 (the failure trace and the negative paths):

| Case | Expected Behavior (source) | Observed |
|---|---|---|
| Missing input: 0-byte CSV | 422 typed `empty_file` (INT-01 §2.1) | **422** `{"detail":{"code":"empty_file","message":"This file is empty…","retryable":false}}`. 0 rows changed in `data_sources`, `raw_api_responses`, `campaigns`, `daily_metrics`, `ga_events` |
| Malformed input: wrong header | 422 typed `invalid_header` | **422** `{"detail":{"code":"invalid_header","message":"Your file is missing required column(s): date, campaign_name, platform, spend, impressions, clicks, conversions, revenue…","retryable":false}}`. 0 rows changed |
| Malformed row inside a valid file | Row-level `parse_warnings`, not a whole-file failure (INT-01 §2.7) | Covered by #16's E2E: 1 warning "not a valid number", 4 of 5 rows kept (`test_connector_to_canonical_e2e.py:118-123`) |
| Error envelope | `{"error":{code,message,user_message,retryable}}` (INT-01 §4.4) | `{"detail":{code,message,retryable}}` for 422; `{"detail":"<string>"}` for 400/401/404 (D-23) |
| Zero values | Allowed (PROD-01 §3: ≥ 0) | Parser rejects negatives only (`parser.py:178-179`). Not separately traced |
| Insufficient data | PROD-01 §3: more than 30% of days missing → INSUFFICIENT_DATA | NOT RUN — no upload reaches analysis; the upload path persists nothing |
| Duplicate records | Idempotent (INT-01 §1.2) | Normalization replay adds 0 rows (contrast trace). A duplicate `raw_api_responses` key is rejected by `idx_raw_api_idempotent` (live insert, rolled back) |
| Cross-tenant data source | Not found, no leak | **404**, 0 rows changed |
| Unauthenticated | 401 | **401** `{"detail":"Not authenticated"}` |
| Contract path from INT-01 | `POST /api/data-sources/csv-upload` | **404**; the endpoint does not exist on the combined branch |
| Database failure / timeout / cancellation | — | NOT RUN — outside the upload path traced. Worker behaviour is TRK-05 scope |
| UI: CSV with a bad header | Error shown (INT-01 §2.1 typed errors) | UI shows "bad_header.csv · 42 B · Ready to import" with no alert. "Continue" goes to the dashboard with **no API request** |

## 12. Testing

### Unit Tests

- **Backend suite:** 228 passed / 9 skipped on `main`, and 252 passed / 9 skipped on the combined branch. The 24 added tests come from:
  - #16: +3 (`tests/unit/data/normalization/test_normalize.py` 4 → 6; `tests/integration/data/test_connector_to_canonical_e2e.py` 1)
  - #18: +13 (`tests/test_connectors_api.py`)
  - #19: +8 (`tests/unit/ai/test_detector.py` 7; `test_detector_evaluation.py` 1)
- **Frontend (vitest):** 1 test on `main` (`apps/web/tests/home.test.tsx`, which asserts a redirect to `/dashboard`). The combined branch has 3; #16 adds `apps/web/tests/entry-flow.test.tsx` (2).
- **Placeholder tests (lead 9):** `apps/backend/tests/unit/test_placeholder.py` and `apps/backend/tests/integration/test_placeholder.py`, each `def test_placeholder(): assert True`. Both were created in `99c668f` (2026-08-23, "chore: initialize Sawakli AI monorepo and CI pipeline"). They count toward the pass totals above.

### Integration Tests

- **Real-Postgres tests that CI always skips:** 9 tests skip unless `TEST_DATABASE_URL` is set: `tests/integration/connectors/oauth/test_postgres_repository.py` (7) and `tests/integration/data/test_entity_normalization.py` (2). `ci.yml` never sets it, so CI reports "9 skipped" on every run. Run locally against a migrated `sawakli_test`: **PASS**, 9/9, on both `main` and the combined branch.
- **Migrations:** CI's "Verify migrations" step (`ci.yml:63-67`) runs after pytest has already upgraded the database (`tests/conftest.py:35`), so it applies 0 migrations. A downgrade is never tested in CI. Locally, `alembic downgrade base → upgrade head` passed (14 steps each way) on both refs.

### Contract validators (QA-01) and the negative test path

All five validators were run from the repo root with `node tests/contracts/<name>.mjs`. Every file comes from a single commit, `50a84e3` (2026-08-28), and none has been changed since.

| Validator | What it really checks | `main` | combined |
|---|---|---|---|
| `validate-db-schema.mjs` | Regex over the migration source: canonical enum values and column names appear in `CREATE TYPE`/`CREATE TABLE`/`add_column`. No types, nullability or constraints | PASS | PASS |
| `validate-backend-models.mjs` | **Nothing.** Prints "PENDING" and `process.exit(0)` (`:13-16`) | exit 0 (placeholder) | exit 0 (placeholder) |
| `validate-ai-schemas.mjs` | **Nothing.** Prints "PENDING" and `process.exit(0)` (`:13-16`) | exit 0 (placeholder) | exit 0 (placeholder) |
| `validate-ui-types.mjs` | Canonical fields and enums are present in `apps/web/src/types/*.ts` | PASS | PASS |
| `test-deliberate-mismatch.mjs` (negative test) | Injects `anomalies.fake_nonexistent_field` and `platform_enum += 'tiktok'` into `canonical.json`, expects `validate-ui-types.mjs` to fail and name both, then restores the file | PASS; `git status` clean afterwards | PASS; `git status` clean afterwards |

Coverage gaps:

- `canonical.json` defines 9 enums and **8 of the 22 tables** created by migrations. It does not cover `daily_metrics`, `ga_events`, `raw_api_responses`, `data_sources` or `feature_daily`.
- The negative test proves only the UI validator can fail. It also edits a tracked file in place, restoring it in `try/catch` (`:39-91`).

### CI wiring (lead 8)

`.github/workflows/` holds only `ci.yml`, whose jobs are documentation-governance, backend, frontend and integration. `grep -c contracts .github/workflows/*.yml` returns `0`, so no job runs `tests/contracts/`. This maps to QA-00.

### Placeholder packages and scaffold

- Empty packages (a 0-byte `__init__.py` only), all from `99c668f`:
  - `sawakli/data/ingestion`
  - `sawakli/shared/contracts`
  - `sawakli/ai/evaluation`
  - `sawakli/ai/simulation`
  - `sawakli/api/v1`
  - `sawakli/connectors/ga4`
  - `sawakli/db/repositories`
- Legacy six-layer skeleton at the repo root: `agent/`, `api/`, `connector/`, `database/`, `ui/`, `worker/` (52 files, each directory with its own Dockerfile). Nothing references them in `docker-compose.yml` or `ci.yml`. They entered `main` through merge `b07cfb3` (D-26).

### E2E Impact

- No E2E test exercises the real upload endpoint through to persistence. The only E2E (#16) inserts `raw_api_responses` with SQL (`test_connector_to_canonical_e2e.py:102-115`) and calls the Data functions directly.
- There is no browser E2E, and there is no seeded login user to run one against (D-22).

## 13. Verification

Commands executed. Environment: Windows 10, Git Bash; Python 3.12.10 venv; Node v24.19.0 / npm 11.17.0; Docker 29.8.1; PostgreSQL 18.6 via `docker compose` using CI's credentials. Run on 29 Sep 2026.

```bash
git clone https://github.com/elfaroukomaradmission-a11y/Sawakli-AI.git Sawakli-AI-trk06
git config core.autocrlf false && git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'
gh pr view <N> --repo elfaroukomaradmission-a11y/Sawakli-AI --json state,reviewDecision,reviews,statusCheckRollup,mergeable,author,title,headRefName,createdAt,updatedAt
POSTGRES_PASSWORD=postgres docker compose up -d --wait postgres
# backend (apps/backend), env as ci.yml:59-61
pip install -e ".[dev]"; ruff check .; ruff format --check .; mypy src; pytest
alembic upgrade head; alembic downgrade base; alembic upgrade head
TEST_DATABASE_URL=…/sawakli_test pytest tests/integration/connectors/oauth/test_postgres_repository.py tests/integration/data/test_entity_normalization.py
# frontend (apps/web)
npm ci; npm run lint; npm run type-check; npm run build; npm test
# integration job (ci.yml:95-134), isolated compose project, then down -v
docker compose build; docker compose up -d postgres; docker compose run --rm api alembic upgrade head; docker compose up -d --wait
curl --fail http://localhost:8000/health; docker exec sawakli-web wget -qO- http://api:8000/health
# combined baseline
git checkout -b trk-06/combined-baseline origin/main; git merge --no-ff pr/16 pr/18 pr/19   # one at a time
bash .github/scripts/check-documentation-governance.sh <base> <head>                     # each PR head checked out
node tests/contracts/{validate-db-schema,validate-backend-models,validate-ai-schemas,validate-ui-types,test-deliberate-mismatch}.mjs
```

### 13.1 Heads and review state (snapshot 2026-09-29 13:56 UTC)

| Ref | SHA | State | Reviews | CI at head |
|---|---|---|---|---|
| `main` | `b4df966e7bc018d4b252886c8c70c1369968b76a` | — | — | [run 34031138067](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/34031138067): success |
| [#16](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/16) (youssefhalawa) | `c069577c175bf329cb873acdde8a3847943c3df2` | OPEN, MERGEABLE | 0 reviews, 0 comments, no decision | [run 34770748925](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/34770748925): 4/4 success |
| [#18](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/18) (ahmed-ibrahem1793) | `3bd89d22705871b7267eefebe997805bfe1ba28d` | OPEN, MERGEABLE | 0 / 0 / none | [run 34998186922](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/34998186922): 4/4 success |
| [#19](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/19) (ahmed-ibrahem1793) | `0ef4e41bf3e4185114618521aa6eb3bf239863f8` | OPEN, MERGEABLE | 0 / 0 / none | [run 35001352077](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/35001352077): 4/4 success |
| [#17](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/17) (ahmed-ibrahem1793) | `a1080e108e99cc92381ad483bcd654694d8f7b7f` | CLOSED 2026-09-15 17:03 UTC by its author | 0 | Documentation governance FAILURE, Backend FAILURE |

Notes on these heads:

- All five SHAs match the heads recorded in the earlier review, so nothing has been pushed since. No force-push, close or reopen events appear on #16, #18 or #19 (`gh api …/issues/N/timeline`).
- #17's head is an ancestor of #19's (`git merge-base --is-ancestor a1080e1 0ef4e41` → true). Both PRs used the branch `AI-02`, and #19 opened 5 minutes after #17 closed.
- GitHub's `mergeable` flag checks each PR against `main` only, so it cannot show the #18/#19 conflict.
- 13 of the 15 merged PRs have zero reviews; only #11 and #12 have one each. #9 (DATA-04) merged with Backend CI = FAILURE, and #10 fixed it.

### 13.2 Gates: `main` vs combined baseline

| Gate | Source | `main` `b4df966` | combined `79f84ba` | Delta |
|---|---|---|---|---|
| `ruff check .` | CI | PASS | PASS | — |
| `ruff format --check .` | CI | PASS (147 files) | PASS (153) | — |
| `mypy src`, SQLAlchemy 2.0.53 (CI-equivalent) | CI | PASS (87 files) | PASS (89) | — |
| `mypy src`, SQLAlchemy 2.1.1 (today's resolution) | CI | **FAIL**: 5 errors in `db/campaigns_lookup.py:37`, `worker/jobs/claim.py:16`, `worker/scheduler/loop.py:125,130,132` | **FAIL**: same 5 | None introduced by the PRs (D-14) |
| `pytest` | CI | PASS 228 / 9 skipped | PASS 252 / 9 skipped | +24 (§12) |
| `alembic upgrade head` | CI | PASS (no-op after pytest) | PASS | — |
| `alembic downgrade base → upgrade head` | extra | PASS | PASS | — |
| 9 CI-skipped real-Postgres tests | extra | PASS 9/9 | PASS 9/9 | — |
| `npm ci` / `lint` / `type-check` / `build` / `test` | CI | PASS / PASS (0 errors, 2 warnings) / PASS / PASS / PASS (1) | same / PASS (3) | +2 tests |
| Integration job (compose, 4 health checks, 2 smoke calls) | CI | PASS | PASS | — |
| Documentation governance | CI (PR-only) | NOT RUN — PR-only gate | PASS (`origin/main..79f84ba`) | — |

Per-PR governance, run with each PR head checked out (the script greps working-tree files, `check-documentation-governance.sh:75`):

- #16: PASS
- #18: PASS
- #19: PASS
- #17: FAIL — `docs/ai/AI-02_Task_Documentation.md` doesn't match `^docs/[^/]+/[A-Z][A-Z0-9]*-[0-9]+-[a-z0-9][a-z0-9-]*\.md$`, so the script reports "no task document"

All four results match CI.

### 13.3 Traces (combined branch, PostgreSQL 18.6, database `sawakli_trace`)

**Normal (API):**

1. register → login → me → `POST /api/connectors/setup` (201, `status: "disconnected"`)
2. Upload the 180-row PROD-01 CSV → **200**, `row_count: 180`, `parse_warnings: []`, all 180 `parsed_rows` returned. The body is 33,161 bytes for an 11,160-byte upload.
3. Row counts before and after the upload, org-scoped and global: **Δ = 0** for `raw_api_responses`, `campaigns`, `daily_metrics` and `ga_events`.
4. `data_sources.status` goes **`disconnected` → `demo_data`** while `sync_status` and `last_synced_at` stay NULL. `GET /api/connectors/{id}/status` returns `connected: false`.

**Failure:** see §11. Every failure case changed 0 rows.

**Contrast:**

- #16's `test_connector_to_canonical_e2e.py`: PASS. It inserts its raw row with SQL.
- Feeding the same 180 rows directly into `staged_row_from_csv_dict` → `normalize_and_upsert_batch` writes 2 campaigns, 180 `daily_metrics` and 180 `ga_events`. A replay adds 0 rows, and `raw_api_responses` stays at 0.
- `normalize_and_upsert_batch` and `staged_row_from_csv_dict` have **no caller in `apps/backend/src/`**.

**UI** (Playwright, clean browser, local `next start` against the local API):

1. `/login`, then "Create an account" leads to `/setup/organization`, where register and login succeed against the real API.
2. `/setup/connector`: selecting the CSV shows "campaign_data.csv · 11 KB · Ready to import". "Continue" goes to `/dashboard`.
3. The dashboard shows mock KPIs ("Total Spend 42,500 EGP", "Summer Sale Campaign"). Settings shows only the profile and organization. There is no source or freshness state anywhere.
4. Across the whole flow the browser made exactly two API calls (register 201, login 200). The UI org has 0 data sources and 0 rows.

**Code evidence for the UI:** `app/(auth)/setup/connector/page.tsx:35-48` keeps the file in React state only, and `:50-61` makes no request.

### 13.4 Task-to-commit register

Field names are verbatim from Notion. Track is blank for every Done card, and only the 2026-09 cards carry it. "Task doc missing" means there is no `docs/<layer>/<TASK-ID>-*.md`; the documentation standard itself only arrived on 2026-09-03 (#12). Test counts are collected test ids, attributed to the PR that added the file.

**Board: Done**

| Task | Member | Due | PR # | Merge commit | Task doc | Tests | Acceptance |
|---|---|---|---|---|---|---|---|
| DEV-01 | El-Farouk Omar | 23 Aug | none (direct commits) | `bfa2a15`, `99c668f` | missing | 2 × `assert True` | **Yes**: compose boots postgres/api/worker/web healthy; CI lints and tests. Caveat: legacy skeleton and two root commits (D-26) |
| INT-01 | Mohamed Hassan | 20 Aug | n/a | not in repo (Notion PDF) | n/a | n/a | **Partial**: against "ownership boundaries … are frozen", its own §5 leaves conflicts #1 (token storage ownership) and #13 (connector_tokens schema) pending, and §1.1 and §2.2 disagree on who writes data_sources (D-24). Owner acknowledgement Unverifiable. Where the repo diverges (D-23, D-24, D-29), the fix belongs to the implementing or deciding tasks (§15) |
| PROD-01 | Mohamed Hassan | 21 Aug | n/a | not in repo (Notion PDF) | n/a | n/a | **Unverifiable**: the KPI, CSV-template and seeded-anomaly lines are met (template matches `parser.py:29-39`), but "approved" and "shared" are not evidenced. The §4.6 demo flow can't be walked yet; that is not PROD-01's scope (seed user: QA-00, D-22; real-data dashboard: UI-04, due 22 Oct) |
| UI-01 | Abdulrahman Ehab | 21 Aug | n/a | not in repo (`UI-wireframes.zip`) | n/a | n/a | **Unverifiable**: attachment not opened (out of TRK-06 scope) |
| UI-02 | Abdulrahman Ehab | 24 Aug | #2 | `4b6e421` | missing | `home.test.tsx`: 1 (from scaffold `99c668f`) | **Partial**: app builds, runs and navigates. Services are mock (`lib/mock-data`). On `main` the auth service was a hard-coded mock |
| API-01 | El-Farouk Omar | 25 Aug | #5 | `3adee87` | missing | `test_auth.py`: 6, `test_org_isolation.py`: 6, `test_security.py`: 2 | **Yes**: register, login and JWT work; isolation tests pass; cross-tenant access returns 404. `API-01_guidance.md:7` maps "Approved demo user/workspace auth path works" to sign-up and log-in, which work. The missing seeded login user (D-22) is QA-00's "browser E2E seed" |
| WORK-01 | El-Farouk Omar | 25 Aug | #3 (rebase-merged; the same worker files also appear in #5) | `4ac4779` | missing | `test_lifecycle.py`: 38 | **Yes (by tests)**. Not traced (TRK-05 scope) |
| WORK-02 | El-Farouk Omar | 27 Aug | #7 | `e739b72` | missing | `test_claim` 2, `test_dedup` 7, `test_loop` 7, `test_retry` 4, `test_timeout` 4 | **Yes (by tests)**. Completed At (28 Aug) is after Due |
| QA-01 | Abdulrahman Ehab | 28 Aug | #8 | `52a94cc` | missing | 5 validators | **Partial**: 2 of 5 validators are placeholders, 8 of 22 tables are covered, and none runs in CI (§12) |
| CONN-01 | Mohamed Hassan | 25 Aug | #1 | `3657dd8` | missing | `test_parser.py`: 14 | **Yes**: typed errors and RawResponse confirmed live. No approved sample file is in the repo |
| CONN-02 | Mohamed Hassan | 27 Aug | #4 | `c4277d7` | missing | 11 + 7 + 14 + 7 (the 7 real-Postgres tests are CI-skipped) | **Yes (boundary)**: crypto, repository, health and the `TokenExchanger` contract are tested. No real provider exchanger exists (`connectors.py:71-97` → 503); #18 records that CONN-02 "does not provide a real provider HTTP implementation" (`connectors.py:74`), and the first real provider read path is CONN-03's Definition of Done (due 29 Oct). The audit author owns CONN-02; the same boundary rule is applied as for API-03's OAuth item |
| API-04 | Mohamed Hassan | 27 Aug | #6 | `19c0cd4` | `docs/api/API-04-analysis-refresh-and-job-status.md` (direct push `b9333b3`) | `test_analysis_refresh` 11, `test_job_status` 8 | **Yes (by tests)** |
| DATA-01 | Ahmed Ibrahem | 23 Aug | none. The SQL zip was ported to Alembic `0001`–`0009` inside #4 | `c4277d7` | missing (Notion `README_DATA01.md`) | via all DB tests | **Yes**: a fresh database builds from migrations; the round trip passes; roles and RLS are present (`0007`) |
| DATA-02 | Ahmed Ibrahem | 23 Aug | none (`0009` in #4) | `c4277d7` | missing (Notion `README_DATA02.md`) | none | **Unverifiable**: the 90-day seed loads (4 campaigns, 360 `daily_metrics` rows). `README_DATA02.md:29` names `generate_demo_dataset.py` as the regeneration script, but it is in neither the export nor the repo, so regeneration was not run. Login users are not in DATA-02's Definition of Done (D-22 → QA-00) |
| DATA-03 | Ahmed Ibrahem | 25 Aug | none | **not in repo** | missing | Notion `test_ingestion.py` (not run) | **Unverifiable**: the Notion `ingestion.py` defines `_persist_raw_response` (`ingestion.py:86`) but was not executed and is not in the repo. Nothing in the repo writes `raw_api_responses`; the production writer is ING-01's Definition of Done ("immutable raw storage", due 15 Oct) |
| DATA-04 | El-Farouk Omar | 3 Sep | #9, #10 | `3ac4589`, `e41f92d` | missing | `test_normalize` 4, `test_adapters` 1, `test_mappings` 4, `test_entity_normalization` 2 (CI-skipped) | **Yes**: normalization and idempotent upsert confirmed (contrast replay). #9 merged with Backend CI red |
| AI-01 | Hussein Elhaddad | 3 Sep | #11 | `b433888` | `docs/ai/AI-01-feature-pipeline.md` | 14 + 11 + 3 | **Yes (by tests)**. The loader reads `daily_metrics`, not `feature_daily` (D-29) |
| AI-03 | Abdulrahman Ehab | 5 Sep | #14 | `8d67c28` | `docs/ai/AI-03-forecasting.md` | 18 + 1 | **Yes (by tests)**. Evaluation figures not re-derived |
| AI-04 | Mohamed Hassan | 7 Sep | #15 | `b4df966` | `docs/ai/AI-04-recommendation-engine.md` | 29 | **Yes (by tests)** |

**Board: Backlog (reconciled 23 Sep; revised deadlines)**

- **DATA-05**: Member youssef halawa. Track "Connector & Data". Due 8 Oct 2026. PR #16, not merged. Doc: `docs/data/DATA-05-canonical-daily-metrics.md`. Tests: `test_normalize.py` +2, `test_connector_to_canonical_e2e.py` 1.
  - Rows follow INT-01: **Met** (in #16).
  - Totals reconcile within tolerance: **Not yet** (DATA-05's own; in window). There is one 5-row, single-org fixture, and neither INT-01 nor PROD-01 records an agreed tolerance.
  - Disallowed PII removed: **Not yet** (DATA-05's own; in window). There is no PII handling or test; doc `:156` says PII is not part of this task, which contradicts this Definition of Done line, and no contract defines "disallowed" PII.
  - Semantics consistent across consumers: **At risk** (in window, incorrect behaviour in PR): D-30, the org-reassigning upsert with no multi-org fixture, which the Entry Contract asks for. D-29 (AI reads `daily_metrics`) is not DATA-05's: no card assigns `feature_daily`.
- **QA-02**: Member youssef halawa. Track "System QA". Due 29 Oct 2026. PR #16, not merged. Doc: `docs/testing/QA-02-connector-to-canonical-e2e.md`. Tests: E2E 1.
  - CSV → raw → staging → canonical: **Not yet**. The raw row is inserted with SQL. Waits on ING-01 (15 Oct), QA-00 (15 Oct) and API-03 (22 Oct), all completion gates; QA-02's window is 9–29 Oct.
  - Totals reconcile, no duplicates: **Met** (fixture scope only).
  - Failure behavior clear: **Not yet**. Only one row warning is asserted. Waits on the same gates; ING-01 must first prove partial failure and retry idempotency.
  - GA4 path included: **Met** (via `ga_events`).
- **UI-03**: Member Abdulrahman Ehab (24 Sep handoff; Youssef Halawa credited and reviews). Track "Frontend". Due 22 Oct 2026. PR #16, not merged. Doc: `docs/ui/UI-03-login-workspace-connector-setup.md`. Tests: `entry-flow.test.tsx` 2.
  - Log in and create workspace: **Met**.
  - CSV upload usable: **Not yet**. No request is made. Required by UI-03's Definition of Done; waits on API-03 (a completion gate), whose upload/status contract UI-03 consumes on 20 Oct ("verify real import and errors Thu 22 Oct").
  - Connection/freshness visible: **Not yet**. None is shown. Waits on API-03's status contract (20 Oct) and ING-01's persisted-readiness status (15 Oct).
- **API-03**: Member Ahmed Ibrahem. Track "Backend". Due 22 Oct 2026. PR #18, not merged. Doc: `docs/api/API-03-connector-api-endpoints.md`. Tests: `test_connectors_api.py` 13.
  - Setup and CSV upload: **At risk** (in window, incorrect behaviour in PR). The endpoint accepts and parses the upload, which meets "Backend initiates connector setup and accepts CSV upload". But the Backend route writes `data_sources.status = 'demo_data'` (`connectors.py:237-251`), a field INT-01 §3 assigns to the Data Layer, and the Entry Contract says "fix PR #18 status now". Persisting rows is not in this Definition of Done line; it arrives through ING-01 (completion gate, due 15 Oct). The response shape and path are ARCH-02's decision (D-23, due 8 Oct).
  - OAuth code passed to Connector: **Met at the boundary**. The route passes the code to the Connector's `TokenExchanger` dependency. No real provider exchanger exists, so it returns 503 (code read); a real provider path is CONN-03's (due 29 Oct).
  - Status returned safely: **Met**.
  - Tokens never in UI or logs: **Met**.
- **AI-02**: Member Hussein Elhaddad (24 Sep handoff; Ahmed Ibrahem credited and reviews). Track "AI". Due 8 Oct 2026. PR #19, not merged; #17 closed. Doc: `docs/ai/AI-02-anomaly-detection.md`. Tests: `test_detector.py` 7, `test_detector_evaluation.py` 1.
  - Ensemble produces severity, direction and score: **Met**.
  - ≥80% recall and ≤5% FPR on seeded data: **Not yet** (AI-02's own; in window, due 8 Oct). The evaluation is a single case (1 campaign, 1 abnormal day) and is not run on the PROD-01 seeded cases.
  - Tenant-scoped grouping: note-only for AI-02. It comes from the 23 Sep reconciliation notes and the 24 Sep handoff note; no AI-02 Definition of Done, Entry Contract or completion-gate line asks for it. `detector.py:71` groups by `campaign_id` only. Organization-isolation tests are AI-07's Definition of Done (due 5 Nov) and tenant-scoped input contracts are ARCH-03's (due 8 Oct).

**New tasks (2026-09)**

- **ING-01** — youssef halawa · Connector & Data · Backlog · due 15 Oct 2026. `Depends On (2026-09)`: ARCH-04, CONN-01, DATA-04, DATA-05. Owns lead 1 (persistence part), leads 2, 3 (server side) and 6, the DATA-03 raw writer, idempotency, tenant scope and reconciliation on seeded CSV (§15).
- **QA-00** — Mohamed Hassan · System QA · Backlog · due 15 Oct 2026. `Depends On (2026-09)`: TRK-06. Owns the placeholder validators, CI wiring (lead 8), the browser E2E seed (D-22), `TEST_DATABASE_URL` in CI (D-15) and the CI migration no-op (D-17) (§15).

### 13.5 The 23 Sep reconciliation notes (author not recorded on the cards) and the review leads

Reconciliation notes, quoted from the Notion export `Notes / Comments`. The cards do not record who wrote them, and their authority is unconfirmed. "Confirmed" means the note describes the code accurately; the Definition-of-Done basis for each item is in §13.4.

| # | Task · note | Verdict | Evidence |
|---|---|---|---|
| 1 | API-03: "Correct false demo_data status on parse-only CSV upload; connect upload to raw/canonical persistence or represent pending state truthfully" | **Confirmed** | §13.3 normal trace; `connectors.py:237-251`. Status write: API-03 Entry Contract and INT-01 §3. Persistence: ING-01 (§13.4) |
| 2 | QA-02: "PR #16 tests seeded raw→canonical, but full CSV upload→raw→staging→canonical path remains unproven" | **Confirmed** | `test_connector_to_canonical_e2e.py:102-115` |
| 3 | UI-03: "login flow exists, but selected CSV is not imported server-side" | **Confirmed** (stronger: no connector call at all) | UI trace, 2 API calls total |
| 4 | DATA-05: "Review canonical metric/GA normalization, reconciliation and PII tests"; entry contract "multi-org fixture" | **Confirmed** | No tolerance, no PII tests, single-org fixture; new D-30 |
| 5 | AI-02: "Complete tenant-scoped grouping by organization + campaign, add cross-tenant regression and evaluation evidence" | **Confirmed** | `detector.py:71`; `test_detector_evaluation.py:16,44-73`. Evaluation: AI-02 Definition of Done. Tenant grouping: note-only for AI-02; AI-07/ARCH-03 by Definition of Done |

Earlier independent review and board leads:

| # | Lead | Verdict | One-line reason |
|---|---|---|---|
| 6 | Nothing writes `raw_api_responses` | **Confirmed** | No reference in `apps/backend/src/`. The only writer is test SQL |
| 7 | #18 returns full `parsed_rows`; INT-01 says `{data_source_id,row_count,parse_warnings}` | **Confirmed** | 33 KB response for 180 rows. The path also differs (INT-01's path → 404) |
| 8 | QA-01 validators exist but no CI job runs them | **Confirmed** | 0 matches for "contracts" in the workflows |
| 9 | Two `assert True` placeholder tests, created in the 23 Aug scaffold commit | **Confirmed** | `99c668f` (2026-08-23), which is a root commit (D-26); 7 empty packages and 2 exit-0 validators also found |
| 10 | #18 and #19 conflict on `apps/backend/pyproject.toml` | **Confirmed** | Cause: mixed line endings plus #18's added `python-multipart` |
| 11 | `feature_daily` exists in migrations but no source file reads or writes it | **Confirmed** | `0003_data_layer_tables.py:218`; no `src/` reference; AI reads `daily_metrics` (D-29) |
| 12 | `ga_events_table` missing from `main`'s `db/tables.py`, added only in #16 | **Confirmed** | `main:db/tables.py` has only `daily_metrics_table:184`; `pr/16:db/tables.py:202` |
| 13 | `raw_api_responses` has no unique constraint on `(data_source_id, endpoint, fetched_at)` | **Refuted** | `0006_indexes_and_constraints.py:82-83` `CREATE UNIQUE INDEX idx_raw_api_idempotent`; a duplicate insert is rejected live |
| 14 | QA-02 note copied from API-03; who owns QA-02? | **Confirmed** (copied note); owner youssef halawa | Both notes begin "Temporarily reassigned from Youssef Halawa…". The live QA-02 card, checked by Mohamed Hassan on 29 Sep, shows Member youssef halawa; the note line is a copy of API-03's, not an ownership change |
| 15 | AI-02 Deliverables cite a #17 commit and an old doc name | **Confirmed** | Deliverables: `AI-02_Task_Documentation.md`, `…/pull/17/changes/1ffd74c…`. `1ffd74c` is also #19's first commit |
| 16 | DATA-03 dropped from QA-02 deps; ING-01 appears instead | **Confirmed** (fields); supersession **Partly confirmed** | QA-02 `Prerequisites` include DATA-03, `Depends On (2026-09)` does not. ING-01's scope covers DATA-03's, but no card states the supersession |

### 13.6 Reviewer decisions (drafted for the task owner; not posted)

| PR | Draft verdict | Basis |
|---|---|---|
| #16 | **Comment** | Gates green. DATA-05's open items are its own and in window (due 8 Oct); QA-02's and UI-03's wait on ING-01 and API-03 (§13.4). D-30 is incorrect behaviour in the PR but latent: current callers cannot trigger it, so it doesn't break another layer as merged today. The request for a two-organization regression test stands (DATA-05 Entry Contract "multi-org fixture"; root `AGENTS.md` cross-tenant test rule). The docs overstate verification (D-25) |
| #18 | **Request changes** | In window, incorrect behaviour in PR: on every upload the Backend route writes `data_sources.status` (`connectors.py:237-251`), which INT-01 §3 ("One writer per table, always") assigns to the Data Layer, so merging would add a second writer to a Data-owned field. API-03's Entry Contract says "fix PR #18 status now". Not part of the basis: row persistence (ING-01's Definition of Done), the INT-01 shape and path divergence (D-23, ARCH-02's decision) and the `pyproject.toml` conflict with #19 (lead 10), which whichever PR merges second resolves |
| #19 | **Comment** | Ensemble solid. Evaluation evidence (AI-02's own Definition of Done, due 8 Oct) not yet done. Tenant grouping is note-only for AI-02 (AI-07/ARCH-03 by Definition of Done). No production caller yet |
| #17 | none | Closed |

No PR gets **Approve**, because none fully meets its task's Definition of Done.

## 14. Known Limitations

### Findings not on the lead list

Each D-number cited in this document is defined by its bullet in this section (here or under "Board and process observations"). The numbers come from the audit's working log, so gaps in the sequence are expected.

- **D-14 Dependency drift:** `pyproject.toml:14` `sqlalchemy>=2.0,<3.0` now resolves to 2.1.1 (PyPI 25 Sep 2026; 2.1.0 was 24 Sep). A CI re-run of unmodified `main` would fail `mypy` (5 errors). CI last passed with 2.0.52/2.0.53. Update 30 Sep: this happened. #20's PR run 36598495262 and the `main` push run 36604830235 (merge `c2b3b62`) failed Backend with the same 5 errors.
- **D-15 Skipped real-Postgres tests:** CI starts Postgres but never sets `TEST_DATABASE_URL`, so 9 real-Postgres tests have never run in CI. They pass locally.
- **D-16 Password in logs:** `alembic/env.py:39` prints the database URL, including the password, to stdout on every run.
- **D-17 No-op migration check:** CI's migration step runs after pytest has already migrated, so it applies nothing, and downgrades are never tested in CI.
- **D-22 No seeded user:** no login user is seeded. The seeded "Nour Fashion Co." org can't be reached through login, so PROD-01's demo flow can't be demonstrated on real data.
- **D-23 Upload contract divergence:** #18's upload path, response fields and error envelope all differ from INT-01 §2.1 and §4.4, and INT-01's own path returns 404.
- **D-24 Status field ownership:** INT-01 §3 gives `data_sources` status fields to the Data Layer (and `db/tables.py:62` says the same), but #18's Backend route writes them. INT-01 §1.1 and §2.2 disagree on whether Backend writes `data_sources` at all.
- **D-25 PR docs overstate status:** `docs/testing/QA-02-…md` says "Implemented and verified" while the board says Backlog and the evidence says unproven. `docs/ui/UI-03-…md` says no upload contract exists, but INT-01 §2.1 defines one.
- **D-26 History and legacy skeleton:** `main` has two root commits (`d522f4d` 19 Aug, `99c668f` 23 Aug). The direct merge `b07cfb3` (3 Sep) joined them, with the old line as first parent, and re-added 52 legacy files (`agent/ api/ connector/ database/ ui/ worker/`) that nothing uses. As a result, `git log --first-parent main` hides PRs #1–#10. Direct pushes to `main` without a PR: `bfa2a15`, `c5f67f8`, `b07cfb3`, `b9333b3`. Whether `main` was force-pushed around 23 Aug is **Unverified** (GitHub push events not queried).
- **D-29 Feature source:** INT-01 names `feature_daily` as the AI feature source, but `ai/features/loaders.py:70` reads `daily_metrics` directly.
- **D-30 Org reassignment in upsert:** #16's upserts reassign `organization_id` on conflict (`upsert.py:240,262`), and no two-organization test exists.
- **D-31 Demo naming:** the UI's demo identity "Fashion Brand X" differs from PROD-01's "Nour Fashion Co.", and the dashboard shows mock data even after a real login.

### Board and process observations

- **D-01 terminology conflict:** `docs/AGENTS.md:48-49`: "Use `Prerequisites` for the current Notion task dependency model. Do not reintroduce the deprecated `Depends On` terminology." Every 2026-09 card: "The one-way “Depends On (2026-09)” relation is authoritative; the old Prerequisites relation is retained as historical context and must not drive activation." The two contradict each other. This register quotes both field names verbatim and does not resolve the conflict. It keeps the heading `## 3. Prerequisites` because CI requires it (`check-documentation-governance.sh:55`).
- **D-13 overlap with TRK-01..05:** all are due 1 Oct.
  - TRK-02 (Ahmed Ibrahem): "Trace one normal request and one failure/tenant case…" and "remaining API-03 work".
  - TRK-04 (youssef halawa): "Map actual raw, staging, canonical writes, dedup and source status…" and "identify the missing production upload handoff".
  - These overlap substantially with §13.3. TRK-01 (UI-03) and TRK-03 (#19) overlap partially.
  - Decision (task owner, 29 Sep): this register keeps its findings independent and evidence-based, and cross-references TRK-01..05 as owners of layer-level detail (§2).
- **Track field:** blank on every Done card.
- **D-32 Location:** this document lives in `docs/testing/`. `DOCUMENTATION_STANDARD.md` §3 describes `testing/` as the home of "cross-cutting test strategy and acceptance guidance"; TRK-06 is cross-cutting, and QA-00 (System QA) depends on it.

### Limits of this audit

- **Board freshness:** board facts are as of the 29 Sep 15:57 export. No live Notion comparison was made, except that the task owner checked the QA-02 Member field on the live card on 29 Sep. Per-card last-edited times are **Unverified** because the export has no last-edited column.
- **Environment:** gates ran on Windows with Python 3.12.10, not CI's Ubuntu. The results matched CI's reported counts wherever CI evidence exists.
- **OAuth:** the OAuth callback was assessed by reading the code, not by execution.
- **Done tasks:** acceptance for Done tasks rests on passing tests unless stated otherwise. Worker, AI-03 and AI-04 behaviour was not traced (TRK-05 and TRK-03 scope).
- **Notion attachments:** the Notion PDFs, zips and DATA-03 `ingestion.py` were read but not executed. `UI-wireframes.zip` was not opened.
- **Test users:** the traces used synthetic users on local databases. Seeded-org behaviour (Nour Fashion) was checked only through row counts, because no login exists for it.

## 15. Follow-Up Tasks

Findings mapped to existing cards. A "candidate" mapping means no DoD line names the item explicitly, so the owner should confirm it.

- `ING-01` — youssef halawa — wire API-03 upload → Data ingestion. Covers:
  - persist `raw_api_responses`, porting or replacing DATA-03's unported writer
  - truthful source/sync state
  - retry idempotency, tenant scope, reconciliation on seeded CSV
  - Findings: leads 1, 2, 3 (server side) and 6; D-24.
- `QA-00` — Mohamed Hassan. Covers:
  - replace the 2 PENDING validators
  - run `tests/contracts/` in CI (lead 8)
  - set `TEST_DATABASE_URL` in CI (D-15)
  - make the migration check test up and down (D-17)
  - publish a browser E2E seed and login user (D-22)
  - Candidates: extend `canonical.json` beyond 8/22 tables; retire the `assert True` placeholders (lead 9); pin or lock backend dependencies (D-14).
- `ARCH-02` — Ahmed Ibrahem — decide the upload request/response and error envelope (INT-01 §2.1 path vs #18's; `parsed_rows` in the response; §4.4 nesting) and the "truthful source state" (D-23, D-24; lead 7).
- `ARCH-04` — youssef halawa — RawResponse persistence decision, Connector-parse vs Data-write split, and "source freshness ownership", including who writes `data_sources.status` (D-24; leads 6 and 13 context).
- `ARCH-03` — Hussein Elhaddad — tenant-scoped AI input and labelled evaluation contracts (lead 5). Candidate: whether AI reads `feature_daily` or `daily_metrics` (lead 11, D-29).
- `ARCH-06` — Abdulrahman Ehab — typed API client and state for ingestion and dashboard; replace mock services; show source status (UI-03 note; D-31).
- `ARCH-01` — Mohamed Hassan — runtime DB credentials. Candidates: stop logging the DB URL (D-16); include the legacy root skeleton in the boundary delta (D-26).
- `DATA-05` — youssef halawa — reconciliation tolerance, PII rule and tests, a two-org regression for the upsert (D-30), then review and merge #16.
- `QA-02` — youssef halawa — real ingress E2E after ING-01 and the corrected API-03; failure and partial-failure assertions; correct the PR doc's "Implemented and verified" (D-25).
- `UI-03` — Abdulrahman Ehab (Youssef Halawa reviews) — call the upload API, show truthful status and freshness, surface upload errors (§11 UI row).
- `API-03` — Ahmed Ibrahem — stop writing `data_sources.status` from the Backend (Entry Contract "fix PR #18 status now"; INT-01 §3); adopt ING-01's ingestion call (completion gate, handoff 20 Oct); align the response once ARCH-02 decides it (lead 7, D-23). The `pyproject.toml` conflict with #19 (lead 10) falls to whichever PR merges second.
- `AI-02` — Hussein Elhaddad (Ahmed Ibrahem reviews) — evaluate on the PROD-01 seeded cases (Definition of Done) and update the Notion Deliverables link from #17 to #19 (lead 15). Grouping by (organization, campaign) with a cross-tenant regression is note-only for AI-02 (23 Sep notes, 24 Sep handoff note); by Definition of Done it belongs to AI-07 (due 5 Nov), with ARCH-03's tenant-scoped input contract (due 8 Oct).
- **Proposed new work (no existing card covers it; owner to be assigned by the project lead):**
  1. Repo hygiene: remove the unused legacy root skeleton and add `.gitattributes` to normalize line endings (D-26, lead 10 cause).
  2. Board hygiene (minor): remove the copied "Temporarily reassigned from Youssef Halawa…" line from the QA-02 card (lead 14), and decide the Track field for Done cards.
  3. A decision on the Prerequisites / "Depends On (2026-09)" terminology conflict between `docs/AGENTS.md` and the board (D-01).

## 16. References and Evidence

- **Notion task:** TRK-06 — Review Integrated Baseline and Present Evidence Register (export `TRK-06 — Review Integrated Baseline and Present Ev 3e57de83a91b8129a006e16fac66ab52.md`).
- **Notion export:** `all notion tasks.zip` (29 Sep 2026 15:57). Property file `📋 Tasks 4a4575b6b6864820924c930cbc9bb116_all.csv`. Cards cited:
  - DATA-05 `…3bc7de83a91b81b18f44de89670278a2.md`
  - QA-02 `…3bc7de83a91b815d8e49e8e4f02db4b4.md`
  - UI-03 `…3bc7de83a91b81f58a98c50412fb9cd4.md`
  - API-03 `…3bc7de83a91b81f08b93e80746b7bd08.md`
  - AI-02 `…3bc7de83a91b812f90a3d45525c40682.md`
  - ING-01 `…3e57de83a91b815b814fefa78c1ab36a.md`
  - QA-00 `…3e57de83a91b8103a1b7caed2b4fe085.md`
  - DATA-03 `…3bc7de83a91b81409d53c1393c75cf0e.md`
  - ARCH-01..06 and TRK-01..05 (Member / Track / Status / Due / DoD only)
- **Live Notion check:** QA-02 Member = youssef halawa, confirmed by Mohamed Hassan on the live card on 29 Sep 2026 (resolves lead 14's owner question).
- **Earlier single-card exports** (29 Sep 15:25–15:38): no content difference from the full export.
- **Board freshness:** every board fact in this register is as of the Notion export of 29 Sep 2026 15:57 (Africa/Cairo). Live Notion was not reachable on 29 or 30 Sep. Cards to re-export before this register is next relied on, because their due dates, entry contracts, handoffs or Definitions of Done drive the scope labels in §13.4: DATA-05, QA-02, UI-03, API-03, AI-02, ING-01, QA-00, ARCH-02, ARCH-03, ARCH-04, ARCH-06, CONN-03, AI-07, UI-04, WORK-03.
- **Contracts:** `INT-01_Canonical_MVP_Contract_Pack.pdf` (§1.1–1.4 p.2–4, §2.1 p.5, §2.7 p.7, §3 p.8, §4.3 p.9, §4.4 p.10); `PROD-01_Month-One_Scope_Freeze.pdf` (§3 p.4, §4.2 p.5, §4.6 p.7); `tests/contracts/canonical.json`.
- **ADRs:** none (`docs/adr/.gitkeep` only).
- **Repository:** `main` `b4df966e7bc018d4b252886c8c70c1369968b76a`. Combined baseline (local only) `79f84ba4f14cf97590ae6bb72396f6230fc4bd6e`, built from merges `178fe3a`, `e9bbfdd`, `79f84ba`.
- **Pull requests:**
  - Open: [#16](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/16) `c069577`, [#18](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/18) `3bd89d2`, [#19](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/19) `0ef4e41`
  - Closed: [#17](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/17) `a1080e1`
  - Merged: #1–#15 with the merge commits listed in §13.4, plus #12 `480ac44` and #13 `10e398f`
- **CI runs:**
  - `main`: [34031138067](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/34031138067) (installed `sqlalchemy-2.0.52`; mypy "Success: no issues found in 87 source files"; pytest "228 passed, 9 skipped")
  - #16: [34770748925](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/34770748925)
  - #18: [34998186922](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/34998186922)
  - #19: [35001352077](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/35001352077)
  - `b9333b3` push: 33972353476 (success)
- **Related technical documentation:** `docs/DOCUMENTATION_STANDARD.md`, `docs/templates/TASK_DOCUMENTATION_TEMPLATE.md`, root and nested `AGENTS.md`, `docs/data/DATA-05-canonical-daily-metrics.md` (#16), `docs/testing/QA-02-connector-to-canonical-e2e.md` (#16), `docs/ui/UI-03-login-workspace-connector-setup.md` (#16), `docs/api/API-03-connector-api-endpoints.md` (#18), `docs/ai/AI-02-anomaly-detection.md` (#19).
- **Test and trace evidence:** commands in §13. Raw logs, trace JSON, screenshots, the audit's working discrepancy log and the review drafts are kept by the task owner and not committed, per root `AGENTS.md` "Temporary Files".
