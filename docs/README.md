# Sawakli AI Technical Documentation

This directory is the permanent technical source of truth for Sawakli AI. Start with the
[`Documentation Standard`](DOCUMENTATION_STANDARD.md) before implementing or reviewing a task.

## Documentation Model

- **Notion** tracks scope, ownership, deadlines, dependencies, progress, and final evidence links.
- **GitHub `/docs`** explains architecture, contracts, technical behavior, decisions, and testing.
- **Source code** contains the implementation and only the comments needed to clarify non-obvious
  behavior.

Important technical information must be maintained here, not only in Notion or attached files.

## Start Here

- [Documentation standard](DOCUMENTATION_STANDARD.md)
- [Technical task template](templates/TASK_DOCUMENTATION_TEMPLATE.md)
- [AI-01 feature pipeline](ai/AI-01-feature-pipeline.md)

## Categories

| Directory | Purpose |
|---|---|
| `architecture/` | System boundaries, major flows, and cross-cutting design |
| `contracts/` | Canonical definitions shared across layers |
| `adr/` | Accepted, superseded, and rejected architecture decisions |
| `ai/` | AI task and layer documentation |
| `api/` | API task and layer documentation |
| `data/` | Ingestion, normalization, persistence, and data task documentation |
| `connectors/` | External provider and connector task documentation |
| `worker/` | Background job and Worker task documentation |
| `ui/` | User interface task and layer documentation |
| `testing/` | Cross-cutting testing strategy and acceptance guidance |
| `demo/` | Maintained demonstration procedures |
| `templates/` | Approved documentation templates |

Directories are created when maintained content exists. Some categories may therefore be absent.
Existing historical directories remain valid until their content is deliberately reconciled with
the standard.
