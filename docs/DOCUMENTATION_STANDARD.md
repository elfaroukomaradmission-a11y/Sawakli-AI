# Sawakli AI Documentation Standard

## 1. Purpose

Documentation is part of implementation, not an afterthought. Every meaningful implementation
task must leave the repository with enough current technical information for another team member
to understand, review, test, operate, and safely extend the behavior.

This standard exists to provide consistency, traceability, and maintainability; prevent conflicting
definitions between layers; record architectural decisions and assumptions; clarify ownership; and
keep code, contracts, and documentation aligned. A task is not complete when the code works only for
its author. It is complete when its behavior and verification evidence are reviewable by the team.

Sawakli AI uses three documentation levels:

1. **Notion — task and project management:** scope, owner, deadline, dependencies, progress, and
   final evidence links.
2. **GitHub `/docs` — permanent technical source of truth:** architecture, contracts, technical
   behavior, task implementation documentation, ADRs, and testing strategy.
3. **Source code — implementation:** docstrings and comments only where behavior is not obvious
   from the code and its public interfaces.

> Notion tells us what was done and why.  
> GitHub documentation explains how the system works.  
> Code contains the implementation.

Important technical information must not exist only in Notion, an attached PDF, a chat thread, a
meeting recording, or a pull request discussion. Move durable technical information into `/docs`
and link to it from those tools.

## 2. Documentation Hierarchy

When sources disagree, use this source-of-truth order:

1. Accepted Architecture Decision Record (ADR)
2. Canonical shared contract documentation
3. Current approved task specification
4. Layer or task technical documentation
5. Code-level comments and docstrings
6. Historical reports and planning material

If two documents conflict, the higher source wins. This priority identifies the governing source;
it does not permit leaving the lower source stale. Correct or clearly mark the stale source in the
same change that resolves the conflict.

Historical reports and planning material provide context only. They must never silently override a
newer canonical decision. Runtime code that contradicts a higher-authority source is a defect until
the code is corrected or the governing decision is deliberately changed and documented.

## 3. Documentation Locations

Use the following structure as the repository grows:

```text
docs/
├── DOCUMENTATION_STANDARD.md
├── README.md
├── architecture/
├── contracts/
├── adr/
├── ai/
├── api/
├── data/
├── connectors/
├── worker/
├── ui/
├── testing/
├── demo/
└── templates/
```

- `architecture/` describes system boundaries, major flows, and cross-cutting design.
- `contracts/` contains definitions shared by multiple layers. Each shared definition has one
  canonical home.
- `adr/` records accepted, superseded, and rejected architectural decisions.
- Layer directories contain task documents and layer-specific behavior.
- `testing/` contains cross-cutting test strategy and acceptance guidance.
- `demo/` contains maintained demonstration procedures, not canonical system contracts.
- `templates/` contains approved documentation templates.

Create a directory when its first maintained document is added. Do not add empty directories only
to make the tree appear complete. Existing historical locations may remain until content is updated;
new task documentation follows this standard and should link to, rather than duplicate, relevant
older material.

## 4. Task Documentation Rule

Every meaningful implementation task must have a technical Markdown document named:

```text
docs/<layer>/<TASK-ID>-<short-name>.md
```

Examples:

```text
docs/ai/AI-01-feature-pipeline.md
docs/ai/AI-02-anomaly-detection.md
docs/data/DATA-03-raw-payload-persistence.md
docs/api/API-05-ai-output-api.md
docs/connectors/CONN-03-ga4-connector.md
docs/worker/WORK-02-worker-reliability.md
docs/ui/UI-06-recommendation-experience.md
```

Use uppercase task IDs, lowercase kebab-case short names, and the layer that owns the behavior. Start
from [`templates/TASK_DOCUMENTATION_TEMPLATE.md`](templates/TASK_DOCUMENTATION_TEMPLATE.md).

The document must be created or updated in the **same pull request** as the implementation. A task
document is required for features, behavioral fixes, migrations, contract changes, and meaningful
refactors. A reviewer may approve an exemption for a truly non-behavioral maintenance change, but
the pull request must state why no task document is needed.

## 5. Documentation Lifecycle

Use this workflow for every implementation task:

```text
Task To Do
↓
Read task
↓
Read all prerequisites
↓
Read relevant canonical contracts / ADRs
↓
Identify conflicts or unclear requirements
↓
Resolve them before coding
↓
Move task In Progress
↓
Create documentation skeleton
↓
Implement
↓
Update documentation as decisions are made
↓
Add tests
↓
Run verification
↓
Perform code/document reconciliation
↓
Open PR
↓
Independent review
↓
CI passes
↓
Merge
↓
Attach GitHub evidence to Notion
↓
Record completion
↓
Task Done
```

Documentation starts before implementation is complete. Creating the skeleton before coding forces
scope, dependencies, contracts, and ownership boundaries to be understood early. Keep it current as
decisions are made; do not reconstruct behavior from memory at the end of the task.

## 6. Pre-Implementation Questions

Before implementation begins, the implementer must be able to answer:

- What does this task own?
- What does it explicitly **not** own?
- What data or components does it read?
- What does it write?
- Who consumes its outputs?
- What shared contracts might it affect?
- Which prerequisites define its behavior?

Record the answers in the task document. If any answer is unclear, implementation should not begin.
Resolve the uncertainty with the affected owner or project leader and update the governing source.

## 7. Canonical Contracts

Shared behavior must be defined once in a canonical contract. Typical canonical contracts include:

- database table fields;
- enums;
- KPI formulas;
- AI input and output fields;
- API response shapes;
- error formats;
- job lifecycle and statuses;
- recommendation statuses;
- organization-scoping rules;
- connector payloads;
- Worker ↔ AI contracts; and
- authentication and session behavior.

Place cross-layer contracts in `docs/contracts/` unless an accepted ADR establishes another
canonical location. Name the contract clearly, state its owner and consumers, and link to the code
or schema that implements it.

Do not copy the same canonical definition into multiple layer documents. Layer and task documents
must link to the canonical contract and document only their own use, validation, transformations,
and exceptions. If a short excerpt is essential for readability, label it as non-canonical and link
to the governing definition.

## 8. Documentation Synchronization Rule

> A code change that changes documented behavior cannot be merged unless the relevant
> documentation is updated in the same PR.

Examples:

| Code change | Required documentation change |
|---|---|
| API field changed | API contract documentation |
| Enum changed | Canonical enum documentation |
| Formula changed | Metric contract documentation |
| Database column changed | Database contract documentation |
| AI feature semantics changed | AI and affected contract documentation |
| Job lifecycle changed | Job contract documentation |

The implementer performs a code/document reconciliation before opening the pull request. The
reviewer independently compares the implementation, tests, task document, canonical contracts, and
ADRs. CI supports this rule but cannot replace human reconciliation.

## 9. Conflict Procedure

When specifications conflict:

1. Stop before implementing the disputed architecture or behavior.
2. Identify and link both conflicting sources.
3. Determine which source has higher authority under the documentation hierarchy.
4. If still unresolved, raise the conflict to the affected owners or project leader.
5. Record the final decision and the reason for it.
6. Update the canonical contract or create or update an ADR.
7. Only then implement.

No developer may silently choose one interpretation. If an urgent temporary decision is necessary,
it still requires an explicit owner, written rationale, known limitation, and follow-up task.

## 10. Documentation Definition of Done

A task is not Done until every applicable item is complete:

- [ ] Technical task document exists or was updated.
- [ ] Scope and non-goals are documented.
- [ ] Prerequisites are documented.
- [ ] Inputs and outputs are documented.
- [ ] Data ownership is documented.
- [ ] Public interfaces are documented.
- [ ] Important formulas and rules are documented.
- [ ] Missing-value and edge-case behavior is documented.
- [ ] Security implications are documented.
- [ ] Tests are documented.
- [ ] Verification commands and results are documented.
- [ ] Known limitations are documented.
- [ ] Follow-up tasks are documented.
- [ ] Canonical contracts were updated if affected.
- [ ] An ADR was added or updated if architecture changed.
- [ ] A reviewer confirmed code and documentation consistency.
- [ ] GitHub documentation and pull request evidence can be linked from Notion.

Use `N/A — <reason>` for an inapplicable template section; do not delete the section or leave an
ambiguous placeholder. A task must not be considered Done without this documentation Definition of
Done.

## 11. Ownership and Review

The implementer owns the accuracy and completeness of the task document and all documentation
changed by the implementation. The owner of a canonical contract approves changes to that contract.
The pull request reviewer owns the independent code/document consistency check and must not approve
based only on CI status.

`CODEOWNERS` identifies the minimum required GitHub reviewers. Ownership does not prevent other
team members from improving documentation, and it does not transfer responsibility away from the
implementer. When ownership is unclear, the project leader assigns an owner before the disputed
change proceeds.

After merge, the task owner adds durable GitHub links to the Notion task: the pull request, task
document, affected contracts or ADRs, and relevant test or CI evidence. Notion records completion;
it does not become a second technical specification.
