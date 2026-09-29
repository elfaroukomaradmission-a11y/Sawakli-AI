# Sawakli AI

Explainable marketing analytics and decision support for startups and small businesses.

Sawakli AI aims to turn campaign data into a clear view of performance, unusual changes,
short-term forecasts, recommendations, and bounded action simulations. The core product keeps
campaign changes under human control; live external writes are outside the core MVP.

This is a graduation project under active development. The repository contains working modules
and development infrastructure, but the complete CSV-to-AI-to-dashboard flow is still being
integrated.

## Start here

- [Current implementation](#current-implementation)
- [Architecture and repository layout](#architecture-and-repository-layout)
- [Run with Docker Compose](#run-with-docker-compose)
- [Local development](#local-development)
- [Testing and CI](#testing-and-ci)
- [Technical documentation](#technical-documentation)
- [Contributing](#contributing)
- [Team](#team)

## Current implementation

Snapshot reviewed on **29 September 2026** against `main` at
[`c2b3b62`](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/commit/c2b3b6260fd9c936363e16bdf15e814b319d9355).
An implemented module does not imply that it is connected to the product flow.

| Area | Present on `main` | Integration still required |
|---|---|---|
| Web | Next.js routes, layout, typed services, and mock campaign/recommendation screens | Real API client, authentication, upload, and analytical data serving |
| API | Registration, login, current-user, analysis-refresh, and job-status routes | Campaign/dashboard and AI-output APIs; production ingestion handoff |
| Data and connectors | CSV parser, OAuth encryption/token utilities, staging adapters, entity normalization and upserts | Upload-to-raw-to-canonical ingestion; live GA4 adapter |
| AI-01 | Organization-scoped CSV/DB loaders and deterministic feature engineering | Production pipeline wiring; features are computed in memory |
| AI-03 | Forecasting, fallback behavior, intervals, and backtest metrics | Output persistence and Worker/API integration |
| AI-04 | Rule-based recommendations and explanation templates | Real anomaly adapter and recommendation persistence |
| Worker | PostgreSQL job claiming, lifecycle, retry, timeout, and polling | Real task dispatch and AI execution; the current executor is a simulation placeholder |
| Database | Alembic schema, roles, constraints, indexes, and demo-data migrations | Runtime role verification and remaining integration contracts |

AI-02 anomaly detection is proposed in [PR #19](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/19),
which is open and unmerged at this snapshot. The anomaly and simulation packages on `main` are
scaffolds, and `ai/pipeline.py` is empty. AI-05 simulation, AI-06 orchestration/persistence, and
AI-07 security/isolation acceptance remain later work.

Other open implementation PRs are
[#16](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/16) (UI/data/E2E work) and
[#18](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/18) (connector setup/upload APIs).
Their code is not part of `main`. The
[TRK-06 baseline register](docs/testing/TRK-06-integrated-baseline-register.md) records the audited
ingestion, evaluation, contract, and CI gaps; consult its dated evidence before treating a PR or
task as accepted.

## Architecture and repository layout

Sawakli AI uses a **modular monolith**. The product has four runtime services: Next.js Web,
FastAPI API, Python Worker, and PostgreSQL. AI, Connector, and Data are internal Python modules,
not independently deployed services. API and Worker use the same backend Dockerfile with
different entry commands. Compose also provides a separate PostgreSQL service for tests.

```mermaid
flowchart TD
    Web["Next.js Web"] --> API["FastAPI API"]
    API --> DB["PostgreSQL: facts and jobs"]
    Worker["Python Worker"] --> DB
    Worker -. "Planned execution handoffs" .-> Modules["Internal AI, Connector, and Data modules"]
    Modules -. "Planned integrated output flow" .-> DB
```

The diagram describes the runtime boundary and intended handoffs. The current Web uses mock
services; the Worker does not yet run the complete analytical pipeline.

| Path | Purpose |
|---|---|
| `apps/web/` | Active Next.js frontend; React, TypeScript, React Query, Vitest |
| `apps/backend/src/sawakli/api/` | FastAPI application and HTTP routes |
| `apps/backend/src/sawakli/worker/` | PostgreSQL job processing and scheduling |
| `apps/backend/src/sawakli/ai/` | Features, forecasting, recommendations, and future analytical modules |
| `apps/backend/src/sawakli/connectors/` | CSV parsing, OAuth utilities, provider adapters |
| `apps/backend/src/sawakli/data/` | Staging, validation, normalization, and canonical-data writes |
| `apps/backend/src/sawakli/db/`, `apps/backend/src/sawakli/shared/` | Database access, models, shared enums/types and contract scaffolds |
| `apps/backend/alembic/` | Versioned PostgreSQL migrations |
| `apps/backend/tests/`, `apps/web/tests/` | Backend and frontend tests |
| `tests/contracts/`, `tests/e2e/` | Contract validators and E2E scaffolding |
| `docs/` | Maintained technical documentation and evidence |
| `.github/` | CI, documentation governance, contribution templates, and CODEOWNERS |
| `docker-compose.yml` | Active local stack and test database |

The root `agent/`, `api/`, `connector/`, `database/`, `ui/`, and `worker/` directories are legacy
scaffolds. The current Compose stack builds from `apps/`; use those active applications for
development. `infrastructure/` and the root `Makefile` currently provide scaffolding rather than
a complete operational command interface.

## Run with Docker Compose

### Requirements

- Git
- Docker Engine or Docker Desktop with Docker Compose v2 (`--wait` support)
- Available host ports: **3000** (Web), **8000** (API), **5433** (development DB from `.env.example`)

Run these commands from the repository root:

```bash
git clone https://github.com/elfaroukomaradmission-a11y/Sawakli-AI.git
cd Sawakli-AI
cp .env.example .env
```

Review `.env`, replace the development password and JWT secret, then build, migrate, and start:

```bash
docker compose build
docker compose up -d --wait postgres
docker compose run --rm api alembic upgrade head
docker compose up -d --wait api worker web
docker compose ps
```

Migrations must run before the Worker begins querying the database. They include demo data;
they do not create a login user for the seeded organization.

| Endpoint | Use |
|---|---|
| [localhost:3000](http://localhost:3000) | Frontend; redirects through the UI login flow |
| [localhost:8000/health](http://localhost:8000/health) | API process health |
| [localhost:8000/docs](http://localhost:8000/docs) | FastAPI interactive API documentation |

For the current mock UI, the synthetic demo login is `demo@fashionbrandx.com` / `demo`.
It is defined in the frontend service and is separate from real API authentication. To exercise
the backend auth flow, register a separate test account through `/api/auth/register` in the API
documentation. Healthy containers and a working mock dashboard do not prove ingestion or AI
integration.

```bash
docker compose logs --tail=100 api worker web
docker compose down
```

### Configuration

Use [`.env.example`](.env.example) as the starting point; keep real `.env` files out of Git.

| Variable | Current behavior |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose PostgreSQL settings; also used to construct API/Worker connection URLs |
| `POSTGRES_PORT` | Host port for the development DB; example is `5433`, container port is `5432` |
| `DATABASE_URL` | Host Python/Alembic connection; Compose overrides it with the internal `postgres:5432` address |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | API authentication settings; forwarded to API and Worker by Compose |
| `API_PORT`, `WEB_PORT` | Host ports, defaulting to `8000` and `3000`; `WEB_PORT` is a Compose option absent from the example file |
| `NEXT_PUBLIC_API_URL` | Intended browser API base URL; current frontend services still use mocks |
| `CONNECTOR_TOKEN_ENCRYPTION_KEY` | Required when using OAuth token utilities; example placeholder is deliberately invalid |
| `APP_ENV`, `APP_NAME`, `API_HOST`, `POSTGRES_HOST` | Listed in the example; the current Compose commands/configuration do not consume all of them |

Compose currently forwards neither `CONNECTOR_TOKEN_ENCRYPTION_KEY` nor a general `.env` file
into the backend container. OAuth integration needs explicit key injection. The Web Dockerfile
builds Next.js before Compose runtime variables are applied, so do not assume that a changed
`NEXT_PUBLIC_API_URL` is embedded in the browser bundle. These are configuration limitations to
resolve with the relevant integration work.

## Local development

Use **Python 3.12** (`>=3.12,<3.13` in the backend manifest) and **Node.js 24** (see `.nvmrc`).

### Backend

From the repository root, start the database, then install the backend:

```bash
docker compose up -d --wait postgres
cd apps/backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn sawakli.api.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows, create the environment with `py -3.12 -m venv .venv` and activate it using
`.venv\Scripts\Activate.ps1`. Keep `DATABASE_URL` pointed at the host DB port in `.env`.
Run `python -m sawakli.worker` in a separate terminal with the same environment when needed.

For schema changes, create a new revision from `apps/backend` and review the generated migration:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Do not rewrite historical applied migrations. For a running Docker stack, execute upgrades from
the repository root with `docker compose exec api alembic upgrade head`.

### Frontend

In another terminal, from the repository root:

```bash
cd apps/web
npm ci
npm run dev
```

## Testing and CI

Use the dedicated test database: backend fixtures migrate it and delete test rows. Do not point
the suite at a development database containing data you want to keep.

Start the test DB from the repository root:

```bash
docker compose up -d --wait postgres-test
```

Then, in the activated backend environment:

```bash
cd apps/backend
export DATABASE_URL='postgresql+psycopg://postgres:change-me@localhost:5434/sawakli_test'
export TEST_DATABASE_URL="$DATABASE_URL"
ruff check .
ruff format --check .
mypy src
pytest
```

`TEST_DATABASE_URL` enables optional PostgreSQL integration tests in addition to the primary
`DATABASE_URL` fixture connection. In PowerShell, use `$env:DATABASE_URL = '...'` and
`$env:TEST_DATABASE_URL = $env:DATABASE_URL` for the equivalent assignments.

Frontend checks, from `apps/web`:

```bash
npm ci
npm run lint
npm run type-check
npm run build
npm test
```

[GitHub Actions](.github/workflows/ci.yml) runs backend, frontend, and Compose integration jobs on
pushes to `main`/`develop` and on pull requests. PRs also run documentation governance unless
exempted by the repository workflow. The integration job migrates PostgreSQL and checks container
health plus API connectivity; it is not the complete product E2E acceptance test.

Known verification limits are recorded in the [baseline register](docs/testing/TRK-06-integrated-baseline-register.md):
backend dependencies use ranges without a lockfile, `TEST_DATABASE_URL` is not set in CI, and
contract validators are not wired into CI (some are placeholders). Check actual workflow results
and skipped tests rather than assuming the entire acceptance suite ran.

## Technical documentation

- [Documentation index](docs/README.md)
- [Documentation standard](docs/DOCUMENTATION_STANDARD.md)
- [AI-01 data access and features](docs/ai/AI-01-feature-pipeline.md)
- [AI-03 forecasting](docs/ai/AI-03-forecasting.md)
- [AI-04 recommendations](docs/ai/AI-04-recommendation-engine.md)
- [API-04 analysis refresh and job status](docs/api/API-04-analysis-refresh-and-job-status.md)
- [TRK-06 integrated baseline and evidence](docs/testing/TRK-06-integrated-baseline-register.md)

Notion tracks ownership, scope, dependencies, dates, and final evidence links. Repository `/docs`
holds permanent technical documentation. Start from the
[revised execution plan](https://app.notion.com/p/3e47de83a91b812dbddfd803ef42dee7) for the current
core roadmap; older Month-One/August windows in historical task material are not current deadlines.
Canonical contracts and accepted ADRs take precedence over historical reports; this README is an
overview, not a replacement for those sources.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md), and the
[documentation standard](docs/DOCUMENTATION_STANDARD.md), plus applicable nested `AGENTS.md` files.

- Create a focused `feat/`, `fix/`, `chore/`, or `docs/` branch from `main`.
- Submit changes through a pull request with actual verification evidence and human review.
- Update relevant task documentation and shared contracts in the same PR as behavioral changes.
- Preserve organization scope, module ownership, migration history, and secret handling.
- Record checks as `PASS`, `FAIL`, or `NOT RUN — <reason>`; do not equate generated code with verified work.

## Team

Graduation project at **Helwan University, Faculty of Engineering**.

| Current track | Team member |
|---|---|
| Project lead / AI | Hussein Mohamed Elhaddad |
| Frontend | Abdulrahman Ehab |
| Backend | Ahmed Ibrahim |
| Connector and Data | Youssef Halawa |
| Worker | El-Farouk Omar |
| System QA | Mohamed Hassan |
| Supervisor | Prof. Samar A. Said |

Track ownership follows the revised execution plan. Original implementation and PR authors remain
credited in Git history and task evidence.

## License

Proprietary — all rights reserved to the Sawakli AI Team. See [LICENSE](LICENSE) for the terms.
