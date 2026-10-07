# AI-02 — Explainable Campaign Anomaly Detection

## 1. Overview

AI-02 implements the Sawakli AI anomaly-detection component. It receives the `FeatureRecord` objects produced by AI-01 and evaluates campaign-day behavior for meaningful abnormalities.

The component exists to identify abnormal campaign behavior while keeping the result interpretable. For each campaign-day it produces an anomaly score, severity, direction, component scores, and human-readable reasons.

AI-02 sits directly downstream of AI-01 in the AI layer. AI-01 defines the loading and feature-engineering boundary; AI-02 consumes that feature output for anomaly detection.

## 2. Scope

### In Scope

- Campaign-level anomaly detection from AI-01 `FeatureRecord` inputs.
- Robust z-score detection using median and MAD.
- IQR-based outlier detection.
- Isolation Forest detection.
- Weighted ensemble anomaly score in the range `[0, 1]`.
- Human-readable severity: `normal`, `low`, `medium`, `high`, `critical`.
- Overall direction: `normal`, `up`, `down`, or `mixed`.
- Explainable reason strings for interpretable detectors.
- Deterministic behavior through a fixed Isolation Forest `random_state`.
- Per-organization/campaign evaluation without baseline or model leakage across tenants.
- Unit tests covering core anomaly behaviors.
- Controlled synthetic evaluation and a separate trace of the complete committed Nour seed.

### Out of Scope

- Data loading and feature engineering; owned by AI-01.
- Forecasting; owned by AI-03.
- Recommendation generation; owned by AI-04.
- Simulation; owned by AI-05.
- Pipeline orchestration and persistent AI-output storage; owned by later AI-layer work.
- REST/API exposure; owned by API/backend tasks.

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| AI-01 — Implement AI Data Access and Feature Engineering | Provides the canonical `FeatureRecord` input consumed by AI-02. |
| DATA-02 — 90-Day Seeded Demo Dataset | Provides the deterministic demo campaign data used for seeded evaluation. |
| INT-01 — Canonical MVP Contract Pack | Governs the canonical data model and layer boundaries used by the upstream data/AI pipeline. |

AI-01 explicitly defines `FeatureRecord[]` as the output flowing into AI-02 and leaves anomaly scoring out of scope for AI-01.

## 4. Architecture

AI-02 consumes already-engineered campaign-day features and evaluates each organization/campaign history independently.

```text
AI-01 FeatureRecord[]
        ↓
Group by organization + campaign; sort each history by date
        ↓
Build feature matrix
        ↓
Robust Z-score ─────┐
IQR detector ───────┼──→ Ensemble score
Isolation Forest ───┘
        ↓
Severity + Direction + Reasons
        ↓
AnomalyResult[]
```

Ownership boundary:

- AI-01 owns loading, validation, and feature engineering.
- AI-02 owns anomaly detection and anomaly-result generation.
- AI-02 does not directly read provider payloads or authentication credentials.
- No persistent database writes are introduced by AI-02 itself.

## 5. Inputs

| Field / Input | Type | Required | Source | Description |
|---|---|---|---|---|
| `records` | `Iterable[FeatureRecord]` | Yes | AI-01 | Campaign-day feature records to evaluate. |
| `contamination` | `float` | No | Caller/default | Isolation Forest contamination parameter; default `0.05`. |
| `random_state` | `int` | No | Caller/default | Isolation Forest seed; default `42` for deterministic behavior. |
| AI-01 feature fields | `Decimal` / nullable | Per AI-01 contract | AI-01 | Includes spend, CTR, CPC, CPA, ROAS, trends, and rolling metrics. |

The detector groups records by `(organization_id, campaign_id)`. Each group is sorted by date before fitting the forest. Mixed-organization batches are isolated; callers remain responsible for authorization. AI-01 nullable features remain nullable; partially missing columns use their observed group median only for Isolation Forest. Entirely unavailable columns are omitted, never replaced with measured zero.

The upstream AI-01 contract retains `organization_id` and `campaign_id` on every record.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `organization_id` | UUID | No | Downstream AI/API | Source organization identifier. |
| `campaign_id` | UUID | No | Downstream AI/API | Campaign identifier. |
| `campaign_name` | `str` | No | Downstream AI/API | Campaign name. |
| `date` | date | No | Downstream AI/API | Campaign-day date. |
| `score` | `Decimal` | No | Downstream AI/API | Final ensemble anomaly score in `[0,1]`. |
| `severity` | `str` | No | Downstream AI/API | Human-readable severity. |
| `direction` | `str` | No | Downstream AI/API | Overall movement direction. |
| `robust_z_score` | `Decimal` | No | Diagnostics | Strongest robust z-score contribution. |
| `iqr_score` | `Decimal` | No | Diagnostics | Strongest IQR contribution. |
| `isolation_score` | `Decimal` | No | Diagnostics | Normalized Isolation Forest contribution. |
| `reasons` | `tuple[str, ...]` | No | Explainability/UI | Human-readable reasons from interpretable detectors. |

The public result object is `AnomalyResult`, a frozen dataclass. This is a campaign-day diagnostic,
**not** a canonical persisted `anomalies` row or AI-04 `AnomalySignal`. It has no `metric_name`,
its performance direction (`up`/`down`) differs from metric direction (`above`/`below`), and it
includes `normal`/`critical` severities absent from the persisted enum. No mapping is invented here.
See [`canonical.json`](../../tests/contracts/canonical.json) and
[AI-04's input boundary](AI-04-recommendation-engine.md). ARCH-03/AI-06 must agree the adapter
before persistence or recommendation enrichment; there is no production caller in this PR.
INT-01 v1.1 also still describes `feature_daily` as the AI input, while the merged AI-01 task
engineers in-memory features from `daily_metrics`. This inherited source conflict is for ARCH-03;
this PR changes neither the shared schema nor AI-01's source path.

## 7. Rules and Semantics

### Detection ensemble

AI-02 uses three detectors:

1. **Robust z-score**
   - Baseline is the historical campaign median.
   - Dispersion uses MAD scaled by `1.4826`.
   - The normalized contribution is capped to `[0,1]` using a six-sigma scale.
   - If historical MAD is zero, an unequal value is treated as maximally abnormal.

2. **IQR**
   - Baseline uses the historical first and third quartiles.
   - The normal interval is `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`.
   - Values outside the interval receive a normalized score capped to `[0,1]`.
   - A zero IQR with a different current value is treated as maximally abnormal.

3. **Isolation Forest**
   - Uses AI-01 features as the model matrix.
   - `n_estimators=200`.
   - Default contamination is `0.05`.
   - Default `random_state=42`.
   - Raw decision values are normalized to `[0,1]`.

### Ensemble weighting

The final score is:

```text
final_score =
    0.40 * robust_z_score
  + 0.20 * iqr_score
  + 0.40 * isolation_score
```

The result is bounded to `[0,1]`.

### Severity

| Score | Severity |
|---|---|
| `< 0.20` | `normal` |
| `0.20–<0.40` | `low` |
| `0.40–<0.60` | `medium` |
| `0.60–<0.80` | `high` |
| `>= 0.80` | `critical` |

### Direction

Direction is inferred from abnormal movement in business-performance features.

- `up`: performance moved in a positive direction.
- `down`: performance moved in a negative direction.
- `mixed`: evidence points in both directions.
- `normal`: no directional abnormality or insufficient history.

### Missing values

`None` from AI-01 is preserved as the missing-value representation.

Missing values are skipped by interpretable detectors. For Isolation Forest only, a partially missing feature is replaced by its observed organization/campaign median. A column with no observations is omitted.

### Insufficient data

Fewer than five observations in an organization/campaign group do not provide a usable forest baseline. In this case the detector returns a normal result with score `0` and reason:

```text
insufficient campaign history
```

Robust Z-score and IQR have a separate gate: at least five strictly earlier observations,
and five non-missing historical values for the feature. Thus early rows can have zero statistical
components even when the complete group has ten records. The forest is retrospective: it fits
all supplied dates in the group, including dates later than the row being scored. These batch
scores are not evidence of causal online detection or a held-out backtest.

### Ordering and determinism

- Organization/campaign groups are evaluated independently.
- Histories are sorted before fitting; output is sorted by organization UUID, campaign UUID, and date.
- Equivalent reordered inputs produce identical output.
- Isolation Forest uses a fixed seed by default.
- Repeating the same input produces the same result.

### Duplicates

AI-02 itself does not create or validate raw duplicate campaign-day records. Duplicate and source-contract validation belong to AI-01.

## 8. Public Interfaces

### `detect_anomalies(records, *, contamination=0.05, random_state=42)`

**Input:** iterable of AI-01 `FeatureRecord` objects.

**Output:** tuple of `AnomalyResult` objects.

**Errors / edge cases:** empty input returns an empty tuple; insufficient campaign history returns normal results rather than raising.

**Side effects:** none.

### `AnomalyResult`

Frozen result dataclass containing the final anomaly result and diagnostic evidence.

## 9. Data Ownership

### Reads

- AI-01 `FeatureRecord` values supplied by the caller.
- AI-01-derived performance and trend features contained in each record.

### Writes

- No persistent database writes by AI-02.

### Must Never Read

- OAuth tokens.
- User passwords.
- Provider credentials.
- Raw provider API payloads.
- Unrelated organizations' records.

### Must Never Write

- Raw campaign data.
- Credentials or tokens.
- Provider secrets.
- AI-01 source tables.
- Historical migrations.

## 10. Security

Organization identity is retained on output. Baselines, feature imputation, and forests are isolated by `(organization_id, campaign_id)`, including when the same campaign UUID appears in two tenants. The regression compares a combined call with independent per-tenant calls.

AI-02 does not handle authentication credentials, OAuth tokens, passwords, or provider secrets.

The component is intended to operate on already-authorized, organization-scoped AI-01 data.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Empty input | Return `()`. |
| Missing optional feature | Skip in statistical detectors; observed group median for partially missing matrix columns; omit entirely missing columns. |
| Zero denominator / undefined ratio | Handled upstream by AI-01 as `None`. |
| Insufficient campaign history (<5 records) | Return normal result with score `0`. |
| Constant historical feature | Different current value receives maximum detector contribution. |
| Zero IQR | Same as above for IQR detector. |
| Duplicate raw campaign/day | Rejected upstream by AI-01. |
| Database failure | N/A — AI-02 does not access the database directly. |
| Provider/API failure | N/A — provider access belongs to connector/data layers. |
| Timeout | N/A — AI-02 detection is an in-process function. |
| Cancellation | N/A — no asynchronous AI-02 interface exists. |

## 12. Testing

### Unit Tests

`tests/unit/ai/test_detector.py` covers:

- empty input;
- insufficient history;
- normal campaign scoring;
- deterministic repeated calls;
- campaign isolation;
- strong downward anomaly detection;
- strong upward anomaly detection.

`tests/unit/ai/test_detector.py` also checks tenant/campaign UUID collisions, shuffled input,
statistical history gates, and missing matrix columns. The 7 October review adds a
hand-calculable nonconstant baseline: history `[1, 2, 3, 4, 5]` and current value `8`
produce robust contribution `0.562076` and IQR contribution `0.166667`. Sparse-history
cases prove that four observed values are insufficient even with six earlier rows, while
five observed values activate both statistical detectors. Current and future values are
excluded from these baselines and gates. The flat-history assertion now proves
`score == 0` and `severity == normal`, not merely that a row is below critical severity.

`tests/unit/ai/test_detector_evaluation.py` passes raw `MetricRecord` fixtures through real AI-01
feature engineering. It covers 30 homogeneous clean campaigns and 30 explicitly injected final-day
events across spend-waste, CTR-drop, and improvement patterns (60 campaigns × 21 days = 1,260 rows).
At the existing fixture threshold `score >= 0.40`, it reports event recall, clean-day FPR, and
clean-campaign FPR with explicit denominators. These simple synthetic fixtures are not the full
DATA-02/PROD-01 acceptance dataset.

`scripts/ai02_evidence.py` parses only the committed migration's literal daily-metrics block,
executes no SQL, engineers features, and traces all 360 Nour observations. It deliberately does
not calculate recall/FPR without approved ground-truth labels.

### Integration Tests

N/A — current AI-02 implementation does not directly perform database I/O. AI-01 owns the database loading path.

### E2E Impact

N/A — no AI-02 REST endpoint or UI integration is part of this task.

## 13. Verification

Independent execution of verification commands on 6 October 2026, Linux / Python 3.12.3,
against prepared commit `a4a7251c20d9ec424b746416bc41b3cdbf695d3f`, which incorporates
`main` at `e5806de5e562a1b11076ae73c026214dcc2d83c3`. This agent verification does not
replace independent human review. A fresh temporary environment was installed with
`uv venv --python python3.12 /tmp/pr19-venv` and
`uv pip install --python /tmp/pr19-venv/bin/python -e 'apps/backend[dev]'` from the root.
Installed numerical versions: NumPy 2.5.3, scikit-learn 1.9.1, SciPy 1.18.1. Commands below
run from `apps/backend` unless marked repository root; `/tmp/pr19-venv/bin/` selects these tools.

| Command | Result | Evidence |
|---|---|---|
| `/tmp/pr19-venv/bin/ruff check . ../../scripts/ai02_evidence.py` | PASS | No lint errors |
| `/tmp/pr19-venv/bin/ruff format --check . ../../scripts/ai02_evidence.py` | PASS | 154 files formatted |
| `/tmp/pr19-venv/bin/mypy src` | PASS | 89 source files; strict configuration retained |
| `/tmp/pr19-venv/bin/pytest tests/unit/ai/test_detector.py tests/unit/ai/test_detector_evaluation.py -q -s` | PASS | 12 tests; synthetic TP 30/30, recall 100%, clean-day/campaign FPR 0% |
| `/tmp/pr19-venv/bin/pytest tests/unit -q` | PASS | 144 tests, 2 dependency deprecation warnings |
| Full `pytest`, PostgreSQL tests, migrations, Compose stack | NOT RUN — PostgreSQL unavailable and Docker daemon inaccessible | `docker info --format '{{.ServerVersion}}'` failed with socket permission denied; `sudo -n docker info --format '{{.ServerVersion}}'` requires a password; no local PostgreSQL installation |
| Nour trace (repository root): `PYTHONPATH=apps/backend/src /tmp/pr19-venv/bin/python scripts/ai02_evidence.py` | PASS | 360 rows across four campaigns |
| Nour recall/FPR acceptance | NOT RUN — approved labels unavailable | DATA-02 attachment currently contains only README; referenced generator/validation JSON absent |
| Documentation governance (repository root): `bash .github/scripts/check-documentation-governance.sh origin/main HEAD` | PASS | Current main comparison includes the AI-02 task document |
| `git diff --check origin/main HEAD` (repository root) | PASS | No whitespace errors |
| CI at local prepublication verification | NOT RUN — awaiting publication at that time | Subsequent run on `57c8009`: [37526973811](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/actions/runs/37526973811) completed PASS; Backend 245 passed / 9 skipped, Frontend 3 passed, documentation and Compose checks passed. These results are scoped to that head; latest-head evidence is in the PR description |

Source recheck on 6 October 2026: the live AI-02 task still requires labeled clean/anomaly
cases before merge and the ≥80% recall / ≤5% FPR target. DATA-02 links only
`README_DATA02.md`, which names `campaign_data.csv`, `generate_demo_dataset.py`, and
`validation_results.json` but supplies no dated labels or clean masks. PROD-01 §4.2 defines
FPR on clean campaigns; its campaign stories are not dated ground truth. Repository files
and fetched branch history contain no referenced generator or validation JSON. No labels,
clean periods, or thresholds were inferred to close this gap.

Nour diagnostic results at the existing fixture threshold `0.40`:

| Campaign | Rows | Flagged days | Maximum score |
|---|---:|---:|---:|
| Summer Collection Push | 90 | 26 | 0.94778520 |
| Winter Pre-Launch | 90 | 28 | 0.83555380 |
| Flash Sale Banner | 90 | 48 | 1.000 |
| Evergreen Basics | 90 | 35 | 0.90441160 |

These counts are **not** TP/FP labels or acceptance metrics. In particular, high flag volume on
Winter Pre-Launch warrants calibration review. Thresholds/formulas have not been tuned to these
outputs. The three former fixture-only claims are superseded by this dated evidence.

### Review follow-up — 7 October 2026

The follow-up changes only tests and this document; algorithms, thresholds and shared
contracts remain unchanged. Live AI-02/DATA-02 task pages, their available discussions,
GitHub reviews/inline comments, repository files and fetched history were rechecked. No
approved dated labels/clean masks or human approval of the revised head were available.
The earlier CI logs identify seven OAuth PostgreSQL repository tests and two Data entity
normalization PostgreSQL tests skipped because `TEST_DATABASE_URL` is unset; these are
NOT RUN, not passes. Docker socket access remains denied locally.

A new temporary environment was installed with
`uv venv --python python3.12 /tmp/pr19-review-venv` and
`uv pip install --python /tmp/pr19-review-venv/bin/python -e 'apps/backend[dev]'`.
From `apps/backend`:

| Command | Result | Evidence |
|---|---|---|
| `/tmp/pr19-review-venv/bin/ruff check . ../../scripts/ai02_evidence.py` | PASS | No lint errors |
| `/tmp/pr19-review-venv/bin/ruff format --check . ../../scripts/ai02_evidence.py` | PASS | 154 files formatted |
| `/tmp/pr19-review-venv/bin/mypy src` | PASS | 89 source files, strict mode |
| `/tmp/pr19-review-venv/bin/pytest tests/unit/ai/test_detector.py tests/unit/ai/test_detector_evaluation.py -q -s` | PASS | 15 tests; synthetic metrics unchanged |
| `/tmp/pr19-review-venv/bin/pytest tests/unit -q` | PASS | 147 tests, two dependency deprecation warnings |
| Root: `PYTHONPATH=apps/backend/src /tmp/pr19-review-venv/bin/python scripts/ai02_evidence.py` | PASS | All 360 observations; diagnostic counts unchanged |
| Seeded recall/FPR acceptance | NOT RUN — approved labels and clean masks unavailable | Existing task entry contract still requires these before merge |

Latest-head remote CI is recorded in the PR description after execution.
Independent human review remains required; additional agent review does not satisfy it.

## 14. Known Limitations

- Full DATA-02/PROD-01 quality acceptance remains incomplete. The attached DATA-02 README gives
  business-level problems/aggregate ROAS, but no exact anomaly dates, clean date masks, generator,
  or `validation_results.json`. These labels must be source-backed before scoring acceptance.
- Controlled synthetic evaluation is homogeneous and deliberately easy; repeating injected patterns
  does not establish real-data accuracy or generalization.
- Isolation Forest uses all supplied dates and min/max-normalizes scores within a group. Future rows
  can change earlier scores; `contamination=0.05` is not a guarantee of 5% ensemble FPR.
- Statistical detectors use all earlier history rather than a rolling baseline; normal seasonal
  changes and sustained regime shifts need labeled evaluation.
- Overall direction combines raw movements with different units and is a diagnostic heuristic,
  not a persisted per-metric direction. Thresholds/formulas remain those submitted in PR #19.
- No persistent outputs, production caller, or AI-04 adapter exist. The agreed output mapping and
  chronic-underperformance demo behavior remain integration/contract gaps, not implemented claims.
- Local PostgreSQL/Compose checks could not run; final-head CI evidence belongs in the PR
  description. Independent human review of the revised changes remains a merge requirement.
- AI-02 remains incomplete and the PR must stay open until source-backed seeded acceptance
  and required independent human review are satisfied, even if CI passes.

## 15. Follow-Up Tasks

- **AI-02 completion blocker — DATA-02/dataset owner:** provide the referenced generator and
  validation JSON (or approved dated labels/clean masks), then run and report full quality metrics.
  Do not mark AI-02 Done solely on the controlled synthetic result.
- **ARCH-03 — project lead/AI and affected owners:** reconcile campaign-day diagnostics with
  canonical per-metric persisted anomalies and AI-04 `AnomalySignal`; agree evaluation granularity,
  threshold, labels, and online versus retrospective semantics.
- **AI-06 — AI owner:** wire the approved adapter, persist outputs, and integrate the Worker.
- **AI-07 — AI owner:** complete broader role/security and isolation acceptance.

## 16. References and Evidence

- [AI-02 Notion task](https://app.notion.com/p/3bc7de83a91b812f90a3d45525c40682)
- [PR #19](https://github.com/elfaroukomaradmission-a11y/Sawakli-AI/pull/19)
- [AI-01 input contract](AI-01-feature-pipeline.md)
- [Canonical schema](../../tests/contracts/canonical.json); applied migration
  `apps/backend/alembic/versions/0004_ai_layer_tables.py`
- [PROD-01](https://app.notion.com/p/3bc7de83a91b810d8199fd0dcf1a57b2),
  [DATA-02](https://app.notion.com/p/3bc7de83a91b813791a2d7a667c6e68d), and
  [INT-01](https://app.notion.com/p/3bc7de83a91b81a18d20f2aa5dfaf3e0) source attachments reviewed
- [Nour trace script](../../scripts/ai02_evidence.py)
- ADR: N/A — no architectural change or new persistence is introduced

Original AI-02 implementation credit remains with Ahmed Ibrahem. Hussein Elhaddad owns the
remaining tenant/evaluation handoff per the approved task notes; the revised patch still needs
independent human review before merge.
