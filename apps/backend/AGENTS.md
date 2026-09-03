# Backend Agent Instructions

These instructions extend the repository-root [`AGENTS.md`](../../AGENTS.md) for all files under
`apps/backend/`. Apply both files. Global security, organization isolation, Git, documentation, and
verification rules remain mandatory.

## Runtime and Tooling

- Read `pyproject.toml` before changing runtime or tool configuration.
- Use the Python version range declared by `project.requires-python`; do not hard-code a conflicting
  version in code, documentation, containers, or CI.
- Follow the current Ruff configuration, including its selected rules and line length.
- Preserve strict mypy compatibility. Do not add broad ignores or weaken strictness to hide typing
  problems.
- Follow the current pytest paths, Python path, and asyncio configuration.
- Keep dependency bounds consistent with `pyproject.toml`. Update dependency metadata deliberately.

## Database Architecture

- Follow existing SQLAlchemy `Session`, model, Core table, and repository conventions.
- Understand the repository's query-only Core metadata and migration strategy before editing schema
  representations.
- Do not introduce a parallel ORM, database client, session framework, or persistence abstraction
  without explicit architectural approval.
- Treat applied Alembic migrations as immutable history; add a new migration for approved schema
  changes.
- Preserve explicit organization scope in every organization-owned read and write, and add
  cross-tenant tests when the access path changes.
- Do not move table ownership or broaden layer access without an approved contract.

## Backend Architecture

Keep API routes, application workflows, persistence, Data, Connector, AI, and Worker concerns
separated. Reuse existing boundaries under `src/sawakli/`.

- Route handlers validate and translate HTTP concerns; do not place unrelated business logic in a
  route merely for convenience.
- Persistence details belong in the established DB or repository boundary.
- Provider parsing and token handling belong to Connector.
- Ingestion and normalization belong to Data.
- Analytical algorithms belong to AI.
- Background job orchestration and scheduling belong to Worker.
- Do not redesign package boundaries opportunistically while implementing a focused task.

## Backend Testing and Verification

Read `pyproject.toml` and `.github/workflows/ci.yml` before selecting checks. From `apps/backend/`,
the current standard commands are:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Start with the smallest relevant test target, then broaden verification in proportion to risk.
Database and integration tests require their configured PostgreSQL environment. Report each actual
result as `PASS`, `FAIL`, or `NOT RUN — <reason>`; never infer results from CI configuration.
