# AI Package Agent Instructions

These instructions extend the repository-root [`AGENTS.md`](../../../../../AGENTS.md) and backend
[`AGENTS.md`](../../../AGENTS.md) for `apps/backend/src/sawakli/ai/`. Apply all three files. This file
specializes AI data, mathematics, evaluation, and task boundaries; it does not weaken any global
security or governance rule.

## Responsibility

The AI package owns only analytical and AI functionality defined by approved AI tasks and
contracts. It may expose typed analytical interfaces for approved consumers.

Do not take ownership of REST endpoints, authentication, OAuth or token handling, provider parsing,
frontend behavior, database schema ownership, or Worker orchestration unless an approved AI
contract explicitly assigns that responsibility. Keep orchestration outside analytical algorithms.

## Data Boundaries

- Read only canonical data allowed by approved task and shared contracts.
- Preserve explicit `organization_id` scope in every organization-owned data path.
- Never read credentials, secrets, access tokens, or refresh tokens.
- Do not consume raw provider payloads unless a current approved contract explicitly requires it.
- Keep data from different organizations and campaigns isolated throughout grouping, windows,
  joins, caches, evaluation, and output construction.
- Do not add persistence or write to another layer's tables merely to simplify an algorithm.

## Model Philosophy

For the current MVP, prefer interpretable, testable approaches whose behavior can be explained to
reviewers and users. Do not add deep-learning, LLM, hosted-model, or other major AI dependencies
unless the approved task explicitly requires them and the architecture change is approved.

Make assumptions, missing-data behavior, minimum-data requirements, deterministic behavior, and
failure modes explicit. Inspect current task documents and contracts before relying on schedule or
phase assumptions; do not hard-code an old Month-One assumption if current documentation has
superseded it.

## Mathematical Semantics

Never invent or casually reinterpret metric, feature, score, confidence, or evaluation formulas.
Use the current canonical contract or approved task documentation. If definitions are missing or
contradictory, follow the root conflict procedure before implementation.

For every formula or time-series transformation:

- add hand-calculable tests where practical;
- define zero-denominator and missing-value behavior explicitly;
- define insufficient-history and date-gap behavior;
- document rolling window bounds, aggregation, ordering, and inclusion semantics;
- prevent state or history from leaking between campaigns or organizations;
- preserve appropriate numeric precision; and
- prove deterministic output for reordered equivalent input where required.

Do not average ratios when the contract requires a ratio of aggregates, impute zero for unknown
values without approval, or permit undefined numeric values to masquerade as valid output.

## Task Boundaries

Implement only the current approved AI task. Existing task documentation is under `docs/ai/`.

- AI-01 feature work must not implement anomaly detection.
- AI-02 anomaly work must not implement forecasting.
- AI-03 forecasting work must not implement recommendations.
- Recommendation work must not execute provider actions.
- Simulation or evaluation work must not silently redefine upstream feature or model contracts.

Use the current task IDs and documentation when available; examples do not override newer approved
task definitions.

## Evaluation and Evidence

AI task documentation must describe inputs, outputs, algorithm, assumptions, limitations,
evaluation method, and deterministic or random behavior. Record dataset scope and evaluation
conditions without exposing organization-owned or sensitive data.

Do not claim model quality, accuracy, lift, confidence, reliability, or production readiness without
executed, reviewable evidence. A plausible output is not validation. Report unavailable evaluation
as `NOT RUN — <reason>` and identify the follow-up needed.
