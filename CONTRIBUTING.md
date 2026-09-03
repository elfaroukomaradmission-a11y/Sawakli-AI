# Contributing to Sawakli AI

## Development Workflow

Sawakli AI follows GitHub Flow.

Create a short-lived branch from `main`:

- `feat/<description>`
- `fix/<description>`
- `chore/<description>`
- `docs/<description>`

All changes must be submitted through a pull request.

AI-assisted contributions must follow [`AGENTS.md`](AGENTS.md), including any nested `AGENTS.md`
that applies to the files being changed. AI-generated work is not exempt from human review.

## Documentation

Documentation is part of implementation. Read the
[`Sawakli AI Documentation Standard`](docs/DOCUMENTATION_STANDARD.md) before starting a meaningful
implementation task.

- Create the task document from
  [`docs/templates/TASK_DOCUMENTATION_TEMPLATE.md`](docs/templates/TASK_DOCUMENTATION_TEMPLATE.md)
  before implementation is complete.
- Add or update the task document in the same pull request as the implementation.
- Link to canonical contracts instead of duplicating shared definitions.
- Resolve conflicting requirements before implementing the disputed behavior.
- Update affected contracts or ADRs in the same pull request.
- Record the verification commands and actual results.

Notion tracks task management and links to final evidence. GitHub `/docs` remains the permanent
technical source of truth.

## Pull Requests

Before opening a pull request:

1. Ensure the code is formatted.
2. Run the relevant tests.
3. Reconcile the implementation, tests, task documentation, contracts, and ADRs.
4. Provide a clear description of the changes and verification evidence.
5. Ensure CI checks pass.

Direct pushes to `main` are not part of the normal development workflow.
