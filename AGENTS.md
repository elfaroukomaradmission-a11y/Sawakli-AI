# AGENTS.md — Sawakli AI

This policy applies to all AI-assisted work in this repository, regardless of the team member or
AI coding tool involved. Consistency, safety, and traceability are more important than speed.

> AI agents are implementation assistants, not project decision-makers.

## Repository Knowledge Map

Read the sources relevant to the task before changing the repository:

- [`README.md`](README.md) — current system overview, architecture, stack, and local workflow.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — branch, pull request, and documentation workflow.
- [`docs/README.md`](docs/README.md) — technical documentation index.
- [`docs/DOCUMENTATION_STANDARD.md`](docs/DOCUMENTATION_STANDARD.md) — mandatory documentation
  governance and Definition of Done.
- `docs/adr/` — accepted architectural decisions when populated.
- Relevant `docs/<layer>/` task documentation, such as the current AI task documents.
- The nearest nested `AGENTS.md` governing the files being changed.

Canonical contracts belong under `docs/contracts/` as they are established. Do not treat chat
history, previous agent output, old PDFs, old reports, comments, or meeting notes as more
authoritative than current canonical repository documentation.

## Authority and Source-of-Truth Order

Use this order when sources disagree:

1. Current explicit user or approved task instruction
2. Accepted ADR
3. Canonical shared contract
4. Current approved task specification
5. Current task or layer technical documentation
6. Existing implementation and tests
7. Historical reports and planning documents

Existing code and tests do not automatically override an explicitly approved newer contract. They
may instead reveal implementation debt. Tool, platform, and security instructions that operate
outside repository content still apply.

## Conflict Procedure

If an architectural or shared-contract contradiction is found:

1. Stop the disputed architectural change.
2. Identify the conflicting sources precisely.
3. Determine whether the authority order resolves the conflict.
4. If it does not, report the conflict to the affected owner or project lead.
5. Request and record a decision.
6. Update the canonical contract or ADR when necessary.
7. Implement only after the contradiction is resolved.

Agents may propose architecture changes. Agents may not silently establish architecture changes.

## Read Before Writing

Before meaningful implementation:

1. Inspect repository status and the current branch.
2. Read the complete task specification, not only its title.
3. Read all prerequisites.
4. Read relevant canonical contracts.
5. Read applicable ADRs.
6. Read every applicable `AGENTS.md`, including the nearest nested file.
7. Inspect the affected implementation.
8. Inspect existing tests and fixtures.
9. Identify affected upstream and downstream layers.

Do not implement from the task title alone. State material assumptions before relying on them.

## Scope Discipline

Implement only the requested task. Do not opportunistically implement future tasks. Record
unrelated technical debt and suggest focused follow-up work without silently expanding scope.

Examples of prohibited scope expansion:

- AI feature engineering must not automatically implement anomaly detection.
- Anomaly work must not automatically implement forecasting.
- Backend must not take ownership of Connector token storage.
- UI must not invent API contracts.
- Worker must not duplicate AI algorithms.
- Connector must not persist into another layer's owned tables without an approved contract.

Avoid unrelated formatting, renaming, dependency updates, or rewrites. Preserve other contributors'
work in a dirty worktree.

## Architecture Rule

Sawakli AI is a modular monolith with a Next.js web application, a FastAPI API, a Python Worker,
PostgreSQL, and internal backend modules. Prefer this architecture unless canonical documentation
says otherwise.

Do not casually introduce microservices, Redis, Celery, Kafka, Kubernetes, a second persistence
system, duplicate caches, another ORM or database abstraction, or new major frameworks. A major
architectural change requires explicit approval and normally an ADR.

## Layer Ownership

- **UI:** user-facing frontend that consumes Backend contracts.
- **Backend/API:** REST, authentication, business-facing workflows, and organization-scoped data
  serving.
- **Connector:** external provider integration, provider translation, and credential or token
  handling according to canonical contracts.
- **Data:** ingestion and canonical normalized marketing facts.
- **AI:** analytical functionality defined by approved AI tasks and contracts.
- **Worker:** background orchestration, job processing, and scheduling.
- **Database:** shared persistence governed by schema and table-ownership rules.

Detailed ownership belongs in canonical contracts and task documentation. Do not duplicate another
layer's responsibility because doing so is easier.

## Organization Isolation

Organization isolation is a hard security invariant. Every query, mutation, job, cache key, and
output involving organization-owned data must preserve explicit organization scope.

This includes campaigns, metrics, jobs, AI outputs, recommendations, and data sources. A query
capable of exposing another organization's data is a critical bug. Never remove organization
filters for convenience or trust an organization identifier supplied by a client without enforcing
the authenticated scope. Add cross-tenant tests whenever a changed data path could cross this
boundary.

## Secrets and Credentials

Never commit, expose, or fabricate passwords, JWT secrets, API keys, OAuth access tokens, refresh
tokens, private keys, or real `.env` content.

Secrets must not appear in logs, API responses, errors, tests, snapshots, fixtures, documentation,
or agent reports. Use the repository's existing environment and configuration mechanisms. Test
values must be clearly synthetic and non-sensitive.

## Database and Migration Rules

Historical Alembic migrations are historical records. Do not casually edit an already-applied
migration to implement new behavior.

For a legitimate schema change:

- add a new migration and preserve migration history;
- follow the repository's current Alembic and SQLAlchemy conventions;
- document table ownership and affected contracts;
- preserve explicit organization isolation; and
- test upgrades and relevant constraints when practical.

Do not invent new tables to avoid understanding the current schema. Do not move table ownership
silently. Read migration comments and current schema sources before changing persistence behavior.

## Shared Contracts

Never invent shared behavior when a canonical contract should exist. Shared behavior includes DB
columns, API fields, enums, metric formulas, AI output schemas, error shapes, job statuses,
recommendation statuses, connector payloads, and authentication or session behavior.

Search canonical documentation and shared code first. If no contract exists, identify the gap and
propose a canonical definition. Do not silently create a project-wide standard inside one route,
component, worker, connector, or AI module.

## Documentation

Compliance with [`docs/DOCUMENTATION_STANDARD.md`](docs/DOCUMENTATION_STANDARD.md) is mandatory.
A code change that alters documented behavior must update the relevant documentation in the same
pull request. Meaningful implementation tasks must create or update their task technical document.

Shared behavior belongs in canonical contracts. Architecture decisions belong in ADRs. Link to
canonical definitions instead of copying them across layer documents. Do not describe planned work
as implemented.

## Testing

Tests are part of implementation. Use the level appropriate to the change: unit, integration,
cross-organization, regression, or end-to-end. Tests must prove behavior, not merely increase
coverage. Mathematical and business rules should use hand-calculable examples where practical.

Do not remove, skip, loosen, or rewrite valid tests merely to obtain green CI. If an approved
contract changes expected behavior, update tests and documentation together and explain why.

## Verification Truthfulness

Report every check with exactly one of these statuses:

- `PASS`
- `FAIL`
- `NOT RUN — <reason>`

Never claim a test passed if it was not executed. Infrastructure unavailable means
`NOT RUN — PostgreSQL unavailable`, not `PASS`.

Do not claim that a push succeeded when it did not, that a remote branch exists when it is only
local, or that a task is fully verified while required checks remain unrun. Include the exact
commands and meaningful failure output.

## Git Rules

Agents must:

- inspect the current branch before editing;
- avoid feature work directly on `main`;
- create or use a task-specific branch from the intended base;
- keep commits focused;
- avoid unrelated modifications; and
- inspect `git diff` and `git status` before finishing.

Recommended branch names are `feature/<task-id>-<description>`, `fix/<task-id>-<description>`, and
`docs/<description>`.

Do not merge into `main` unless explicitly instructed. Do not force-push shared branches, rewrite
another contributor's commits, delete another member's work, or push unrelated scratch files. A
request to commit or push does not imply permission to merge.

## Pull Request Rules

One pull request should represent one coherent change. It must report purpose, implementation,
architecture impact, affected contracts, tests, actual verification, documentation, limitations,
and follow-ups.

AI-generated work still requires human review. Shared-contract changes require review by affected
layers. Security-sensitive, cross-layer, migration, and other critical work requires independent
review appropriate to its risk.

## Dependencies

Do not add dependencies automatically. Before adding one:

1. Check whether the standard library or current repository already solves the problem.
2. Explain why the dependency is necessary.
3. Assess runtime, security, licensing, and maintenance impact.
4. Follow current version-pinning and lockfile conventions.
5. Document the reason and affected deployment surface.

Major frameworks require explicit architectural approval and normally an ADR.

## Error Handling

Do not silently swallow failures. Preserve useful developer information without leaking secrets or
organization-owned data. Use canonical error shapes when applicable. Do not convert errors,
timeouts, incomplete data, or provider failures into fabricated successful defaults.

## Determinism

Where deterministic behavior is required, the same input and configuration must produce the same
output. Do not introduce uncontrolled randomness, time dependence, unordered iteration, or hidden
global state. When randomness is intentionally required, use and document controlled seeds and
evaluation conditions.

## Temporary Files

Do not commit patch-transfer files, scratch files, logs, temporary exports, editor files, local
databases, test caches, generated output, or accidental artifacts. Before completion, inspect:

```bash
git status
git diff
```

Every changed file must belong to the task.

## AI Agent Conduct

AI agents are not project decision-makers. Agents must distinguish facts from assumptions, state
material assumptions, report blockers honestly, avoid false completion, avoid unnecessary rewrites,
preserve unrelated work, prefer clear maintainable code over clever abstractions, and leave
human-reviewable evidence.

Agents must not silently reinterpret architecture, invent shared contracts, hide failed tests,
fabricate verification, expand scope without reason, overwrite another member's work, or treat
generated code as automatically correct.

## Completion Checklist

- [ ] Requested scope is implemented.
- [ ] No unrelated work was added.
- [ ] Layer boundaries and shared contracts are respected.
- [ ] Documentation was created or updated as required.
- [ ] Tests were added or updated where behavior changed.
- [ ] Relevant quality gates were run.
- [ ] Results are reported truthfully with approved status language.
- [ ] Limitations are documented.
- [ ] Follow-up work is identified.
- [ ] `git diff` was reviewed.
- [ ] `git status` contains only intentional files.
- [ ] No temporary or generated artifacts are included.
- [ ] `main` is unchanged unless the user explicitly requested otherwise.

## Final Agent Report

An implementation agent's final report must include:

1. Branch name
2. Commit SHA, if committed
3. Files added
4. Files modified
5. Architectural approach
6. Contracts affected
7. Tests added
8. Verification commands and `PASS`, `FAIL`, or `NOT RUN — <reason>` results
9. Documentation updated
10. Known limitations
11. Follow-up work
12. Completion status

Do not invent evidence for an empty category; report `None` or an honest `NOT RUN — <reason>`.

## Nested Instructions and Local Overrides

More specific `AGENTS.md` files may exist deeper in the repository. Read the nearest applicable
instructions before editing a subtree. Nested files extend and specialize this policy; they do not
replace it and must not weaken global security, organization isolation, verification honesty, Git
safety, or documentation governance.

`AGENTS.override.md` files are ignored local or private preferences, not team policy. Do not commit
them. An override may add local workflow guidance but must never deliberately bypass security,
tenant isolation, verification honesty, or repository governance.
