# Documentation Agent Instructions

These instructions extend the repository-root [`AGENTS.md`](../AGENTS.md) for all files under
`docs/`. Apply both files. They specialize technical-documentation rules and do not weaken global
security, Git, verification, or governance requirements.

## Documentation Standard

Follow [`DOCUMENTATION_STANDARD.md`](DOCUMENTATION_STANDARD.md) and use the approved task template
for meaningful implementation tasks. Documentation starts before implementation is complete and is
updated in the same pull request as changed behavior.

## Canonicality

Shared definitions belong in `docs/contracts/` when established. A task or layer document links to
the canonical definition instead of copying fields, enums, formulas, statuses, error shapes, or
ownership rules. If no canonical contract exists, identify the gap rather than creating competing
definitions in multiple documents.

## ADR History

Do not rewrite an accepted ADR to make history appear different. Create a new ADR that supersedes
the old decision, preserve links in both directions, and state the transition impact. Corrections
that do not change the decision must remain clearly distinguishable from a new architectural choice.

## Accuracy and Lifecycle Language

When relevant, label functionality or decisions as `Proposed`, `Accepted`, `Implemented`,
`Deferred`, `Deprecated`, or `Superseded`. Do not describe planned, mocked, partially implemented,
or unverified functionality as implemented.

Verify technical claims against current code, tests, contracts, and accepted ADRs. Historical
reports are context, not authority over current canonical documentation.

## Verification Language

Use exactly:

- `PASS`
- `FAIL`
- `NOT RUN — <reason>`

Record only commands actually executed and evidence actually observed. A link to CI is evidence
only when the referenced run exists and has the reported result.

## Terminology

Use `Prerequisites` for the current Notion task dependency model. Do not reintroduce the deprecated
`Depends On` terminology. Use consistent Sawakli layer names and link to the governing source when
a term has contract-level meaning.
