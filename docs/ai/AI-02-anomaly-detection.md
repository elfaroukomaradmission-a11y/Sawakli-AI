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
- Per-campaign evaluation without leakage across campaigns.
- Unit tests covering core anomaly behaviors.
- Seeded evaluation test covering the AI-02 acceptance thresholds.

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

AI-02 consumes already-engineered campaign-day features and evaluates each campaign independently.

```text
AI-01 FeatureRecord[]
        ↓
Group records by campaign
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

The detector evaluates records independently by campaign. AI-01 nullable features remain nullable; when the machine-learning matrix requires a value, missing features are replaced with the campaign median only for the Isolation Forest matrix and are not treated as measured zero.

The upstream AI-01 contract retains `organization_id` and `campaign_id` on every record.

## 6. Outputs

| Field / Output | Type | Nullable | Consumer | Description |
|---|---|---|---|---|
| `organization_id` | object/UUID | No | Downstream AI/API | Source organization identifier. |
| `campaign_id` | object/UUID | No | Downstream AI/API | Campaign identifier. |
| `campaign_name` | `str` | No | Downstream AI/API | Campaign name. |
| `date` | date-like | No | Downstream AI/API | Campaign-day date. |
| `score` | `Decimal` | No | Downstream AI/API | Final ensemble anomaly score in `[0,1]`. |
| `severity` | `str` | No | Downstream AI/API | Human-readable severity. |
| `direction` | `str` | No | Downstream AI/API | Overall movement direction. |
| `robust_z_score` | `Decimal` | No | Diagnostics | Strongest robust z-score contribution. |
| `iqr_score` | `Decimal` | No | Diagnostics | Strongest IQR contribution. |
| `isolation_score` | `Decimal` | No | Diagnostics | Normalized Isolation Forest contribution. |
| `reasons` | `tuple[str, ...]` | No | Explainability/UI | Human-readable reasons from interpretable detectors. |

The public result object is `AnomalyResult`, a frozen dataclass.

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

Missing values are skipped by interpretable detectors. For Isolation Forest only, a missing feature is replaced by that feature's campaign median so that missing data is not confused with zero.

### Insufficient data

Fewer than five campaign observations do not provide a usable baseline. In this case the detector returns a normal result with score `0` and reason:

```text
insufficient campaign history
```

### Ordering and determinism

- Campaigns are evaluated independently.
- Final results are sorted deterministically by campaign ID and date.
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

Organization identity is retained on the output and campaigns are evaluated independently to preserve tenant boundaries.

AI-02 does not handle authentication credentials, OAuth tokens, passwords, or provider secrets.

The component is intended to operate on already-authorized, organization-scoped AI-01 data.

## 11. Error and Edge-Case Behavior

| Case | Expected Behavior |
|---|---|
| Empty input | Return `()`. |
| Missing optional feature | Skip in interpretable detectors; campaign-median imputation only for the Isolation Forest matrix. |
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

`tests/unit/ai/test_detector_evaluation.py` covers the seeded evaluation acceptance target using a deterministic seeded anomaly fixture.

### Integration Tests

N/A — current AI-02 implementation does not directly perform database I/O. AI-01 owns the database loading path.

### E2E Impact

N/A — no AI-02 REST endpoint or UI integration is part of this task.

## 13. Verification

Commands executed from:

```text
Sawakli-AI/apps/backend
```

Environment:

```text
Windows
Python 3.12.10
pytest 8.4.2
```

### AI-02 tests

```bash
py -3.12 -m pytest tests/unit/ai/test_detector.py tests/unit/ai/test_detector_evaluation.py -v -s
```

Result:

```text
8 passed
Recall: 100.00%
False-positive rate: 0.00%
```

### Full AI unit suite

```bash
py -3.12 -m pytest tests/unit/ai -v -s
```

Result:

```text
80 passed, 1 warning
```

### Ruff

The implementation reached a single import-order Ruff issue after the unused imports were corrected. The reported issue is formatting-only and is fixable by Ruff.

### Mypy

A `sklearn.ensemble` missing-stubs/`py.typed` warning was reported during `mypy src`. Existing `jose`/`passlib` per-module configuration warnings were also present in `pyproject.toml`.

The mypy result was therefore not a clean pass at the time of this report.

### Real DATA-02 evaluation

A full recall/false-positive evaluation against the complete DATA-02 360-row dataset was **not completed** because the seeded migration does not expose explicit anomaly ground-truth labels in its searchable content. The migration contains the 90-day Nour Fashion Co. data, but the ground-truth anomaly labels required to calculate recall and false-positive rate were not identified.

Therefore, the reported 100% recall / 0% false-positive result is for the deterministic seeded evaluation fixture in `test_detector_evaluation.py`, not for the full 360-row dataset.

## 14. Known Limitations

- The current acceptance test is a small deterministic seeded fixture rather than a complete labeled evaluation over all 360 DATA-02 rows.
- Explicit anomaly ground-truth labels for DATA-02 still need to be identified before a real-dataset recall/FPR claim can be made.
- Isolation Forest relies on scikit-learn typing support that is not fully recognized by the current mypy environment.
- No persistent anomaly-output storage is implemented in AI-02 itself.

## 15. Follow-Up Tasks

- DATA-02 / dataset owner — provide or document explicit anomaly ground-truth labels for the 90-day seeded dataset so full recall/FPR evaluation can be completed.
- AI-06 — persist AI outputs when the AI pipeline orchestration/output-persistence task is implemented.

## 16. References and Evidence

- Notion task: `AI-02 — Explainable Campaign Anomaly Detection`.
- Canonical prerequisite: `AI-01 — Implement AI Data Access and Feature Engineering`.
- DATA-02 seeded dataset: 90-day Nour Fashion Co. demo dataset.
- Implementation: `apps/backend/src/sawakli/ai/anomaly/detector.py`.
- Unit tests: `apps/backend/tests/unit/ai/test_detector.py`.
- Evaluation test: `apps/backend/tests/unit/ai/test_detector_evaluation.py`.
- AI-01 completion report: documents the `FeatureRecord` contract and the AI-01 → AI-02 downstream boundary.
- Evidence: 8 AI-02 tests passed with 100% recall / 0% false-positive rate on the current seeded fixture; 80 AI unit tests passed overall.
