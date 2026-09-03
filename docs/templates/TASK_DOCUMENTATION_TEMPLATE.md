# TASK-ID — Task Name

<!--
Copy this file to docs/<layer>/<TASK-ID>-<short-name>.md.
Replace every placeholder. Use "N/A — <reason>" where a section does not apply.
Link to canonical contracts instead of duplicating them.
-->

## 1. Overview

Explain:

- what the component does;
- why it exists; and
- where it fits in Sawakli AI.

## 2. Scope

### In Scope

- ...

### Out of Scope

- ...

Explicitly identify responsibilities belonging to other tasks or layers.

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| ... | ... |

List relevant ADRs and canonical contracts.

## 4. Architecture

Explain the component's position in the system.

Use a simple flow when useful:

```text
Input
↓
Component
↓
Output
```

Clearly document ownership boundaries.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

Include validation, organization scope, nullable behavior, and source.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

Do not document fields that do not exist.

## 7. Rules and Semantics

Document formulas, algorithms, calculations, ordering rules, status transitions, and other
meaningful behavior.

Clearly define:

- missing values;
- zero denominators;
- insufficient data;
- duplicates;
- ordering; and
- deterministic behavior where applicable.

Where a canonical contract exists, link to it instead of redefining it.

## 8. Public Interfaces

Document only meaningful externally consumed interfaces:

- functions;
- classes;
- REST endpoints;
- events;
- jobs; and
- database reads and writes.

For each interface, explain its input, output, errors, and side effects. Do not document every
private helper.

## 9. Data Ownership

### Reads

- ...

### Writes

- ...

### Must Never Read

- ...

### Must Never Write

- ...

This section is mandatory.

## 10. Security

Document applicable organization isolation, authentication, authorization, secrets, OAuth tokens,
sensitive fields, database permissions, and trust boundaries.

If there are no special security implications, explicitly say so.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Missing input | ... |
| Malformed input | ... |
| Zero values | ... |
| Insufficient data | ... |
| Duplicate records | ... |
| Database failure | ... |
| Provider or API failure | ... |
| Timeout | ... |
| Cancellation | ... |

Remove irrelevant example rows only after recording why the case cannot apply.

## 12. Testing

### Unit Tests

- ...

### Integration Tests

- ...

### E2E Impact

- ...

Document acceptance behavior, not merely filenames.

## 13. Verification

Commands executed:

```bash
...
```

Results:

- Command, date, environment, and outcome: ...
- CI run or pull request evidence: ...

Do not claim checks that were not run. Explain any omitted or failed verification.

## 14. Known Limitations

- ...

Use `None known` only after considering production, data, security, and operational limits.

## 15. Follow-Up Tasks

- `TASK-ID` — owner — reason or dependency

Use `None` when no follow-up work is required. Do not hide required completion work here.

## 16. References and Evidence

- Notion task: ...
- Pull request: ...
- Canonical contracts: ...
- ADRs: ...
- Related technical documentation: ...
- Test or CI evidence: ...
