# Sawakli AI

**Sawakli AI is an explainable, AI-powered marketing analytics and decision-support platform for startups and SMBs.**

## Problem & Value Proposition

Small and medium marketing teams generate campaign data across many disconnected tools, but rarely have the time or expertise to turn that data into clear, trustworthy decisions. Sawakli AI connects to a business's marketing data sources and turns raw metrics into **explainable** insight: what changed, why it changed, what's likely to happen next, and what to do about it — without requiring a data science team to interpret the output.

## Core Capabilities

- **Dashboard** — a unified view of marketing performance across connected data sources.
- **Anomaly Detection** — surfaces unusual shifts in campaign metrics as they happen.
- **Forecasting** — projects near-term performance trends from historical data.
- **Recommendations** — suggests concrete next actions based on detected patterns.
- **Simulations** — lets a user model the likely impact of a change before making it.

The system deliberately does **not** auto-execute campaign changes in its MVP — every insight and recommendation is left in the user's hands to review and act on.

## Architecture

Sawakli AI is built as a **modular monolith**: four runtime services, with clear internal module boundaries so the system can be split into separate services later if scale ever requires it.

```
Browser
  |
  v
Next.js Web  ------------------------------->  FastAPI API  ------->  PostgreSQL
                                                     |
                                               creates jobs
                                                     |
                                                     v
                                            Background Worker
                                                     |
                                    +----------------+----------------+
                                    v                v                v
                              Connectors          Data             AI
                              (internal)        (internal)      (internal)
                                    |
                                    v
                               PostgreSQL
```

**Runtime services:** `web` (Next.js), `api` (FastAPI), `worker` (Python background process), `postgres`. The API and Worker share a single backend image and differ only by the command each container runs.

**Internal backend modules** (not separate services): `ai` (features, anomaly detection, forecasting, recommendations, simulation, evaluation), `connectors` (CSV, OAuth, GA4), `data` (ingestion, staging, normalization, validation), `db` (session + repositories), `shared` (contracts, enums, types).

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Vitest |
| Backend | Python 3.12, FastAPI, SQLAlchemy, psycopg |
| Database | PostgreSQL 18, Alembic (versioned migrations) |
| Infrastructure | Docker, Docker Compose |
| CI/CD | GitHub Actions (backend, frontend, integration jobs), pre-commit |
| Code quality | Ruff, mypy (backend) · ESLint, TypeScript (frontend) |

## Repository Structure

```
Sawakli-AI/
├── apps/
│   ├── web/                # Next.js frontend
│   │   └── src/
│   │       ├── app/, components/, features/, hooks/, lib/, services/, types/, styles/
│   └── backend/             # FastAPI + Worker (shared Python backend)
│       └── src/sawakli/
│           ├── api/         # HTTP interface
│           ├── worker/      # background process
│           ├── ai/          # internal AI module
│           ├── connectors/  # internal connector module
│           ├── data/        # internal data module
│           ├── db/          # persistence / repositories
│           └── shared/      # contracts, enums, types
├── docs/                    # architecture, api, database, demo notes, ADRs
├── infrastructure/          # docker & operational scripts
├── tests/e2e/               # end-to-end tests
├── .github/                 # CI workflows, issue/PR templates, CODEOWNERS
└── docker-compose.yml
```

## Quick Start

```bash
git clone https://github.com/elfaroukomaradmission-a11y/Sawakli-AI.git
cd Sawakli-AI
cp .env.example .env
docker compose up --build
```

Once all four containers report healthy (`docker compose ps`):
- Web: [http://localhost:3000](http://localhost:3000)
- API health check: [http://localhost:8000/health](http://localhost:8000/health)

## Environment Variables

Defined in `.env.example`:

| Variable | Purpose |
|---|---|
| `APP_ENV`, `APP_NAME` | Application identity/environment |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL connection |
| `DATABASE_URL` | Full SQLAlchemy connection string used by the API and Worker |
| `API_HOST`, `API_PORT` | FastAPI bind address |
| `NEXT_PUBLIC_API_URL` | API base URL the frontend calls |

Copy `.env.example` to `.env` and adjust values for your local setup before running Docker Compose.

## Database Migrations

Migrations are managed with Alembic from `apps/backend`:

```bash
cd apps/backend
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Or, against the running Docker stack, without a local Python environment:

```bash
docker compose exec api alembic upgrade head
```

## Testing & Quality

**Backend** (from `apps/backend`):
```bash
ruff check .            # lint
ruff format --check .   # format check
mypy src                # type check
pytest                  # tests
```

**Frontend** (from `apps/web`):
```bash
npm run lint
npm run type-check
npm run build
npm test
```

All of the above run automatically in CI on every push and pull request, alongside an integration job that builds all four Docker images and verifies the full stack starts healthy.

## Development & Pull Request Workflow

Sawakli AI follows **GitHub Flow** — see [`CONTRIBUTING.md`](./CONTRIBUTING.md) for full details.

### AI-Assisted Contributions

Before using an AI coding agent, read [`AGENTS.md`](./AGENTS.md),
[`CONTRIBUTING.md`](./CONTRIBUTING.md), and the
[`Documentation Standard`](./docs/DOCUMENTATION_STANDARD.md). AI-generated changes require the
same human review, testing, documentation, and verification as any other contribution.

- Branch from `main` using `feat/`, `fix/`, or `chore/` prefixes.
- All changes go through a pull request — no direct pushes to `main`.
- CI must pass, and the code must be linted/formatted, before merge.

## Demo Flow & Project Status

The intended end-to-end flow: a user connects a marketing data source (starting with CSV import and a read-only GA4 connector) → the platform ingests and normalizes the data → the AI layer detects anomalies, generates forecasts, and produces recommendations → the dashboard presents all of it in one place, with simulations available to test hypothetical changes before acting on them.

The project follows a modular-monolith architecture with a fully containerized development environment (Web, API, Worker, PostgreSQL) and a three-job CI pipeline (backend, frontend, integration) validating every change. Development is ongoing as part of the Sawakli AI graduation project.

## Team & Academic Context

Sawakli AI is a graduation project at **Helwan University**, Faculty of Engineering, developed by a six-person team over a one-month MVP execution plan.

| Role | Name |
|---|---|
| Backend / DevOps | Elfarouk Omar |
| *(add remaining teammates here)* | |
| Supervisor | *(add supervisor name here)* |

## License

This project is proprietary. All rights reserved to the Sawakli AI Team — see [`LICENSE`](./LICENSE) for details.