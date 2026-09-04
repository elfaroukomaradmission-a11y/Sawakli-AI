# AI-03 — Forecasting Module

## 1. Overview

AI-03 is the deterministic, in-memory forecasting boundary for campaign `spend`,
`conversions`, and `roas`. It consumes AI-01 `FeatureRecord` values and returns
7-, 14-, and 30-calendar-day projections plus comparable backtest error metrics.
It creates no database records and has no worker integration.

## 2. Scope

### In Scope

- Typed forecast and evaluation contracts.
- Moving average, OLS linear regression, and fixed-seed Random Forest forecasts.
- Deterministic fallback selection, confidence intervals, and backtesting.
- Read-only evidence export from the seeded Nour Fashion Co. data.

### Out of Scope

- AI-02 anomaly detection, AI-04 recommendations, AI-05 action simulation, and
  AI-06 orchestration.
- Writes to `forecasts` or `model_runs`, any migration, API endpoint, or Worker wiring.
- Rich AI-01 rolling/trend features as Random Forest inputs.

## 3. Prerequisites

| Task / Contract | Why Required |
|---|---|
| [AI-01 feature pipeline](AI-01-feature-pipeline.md) | Sole input boundary: its validated, organization-scoped `FeatureRecord` output provides campaign-day metric observations. |
| [`tests/contracts/canonical.json`](../../tests/contracts/canonical.json) | The persisted `forecasts` table informs names only; it is not written by AI-03. |

## 4. Architecture

```text
AI-01 FeatureRecord values
        ↓
AI-03 validation / campaign + metric grouping
        ↓
Random Forest → Linear Regression → Moving Average → insufficient_history
        ↓
ForecastRecord / ForecastEvaluation (in memory only)
```

`generate_forecasts()` and `evaluate_forecasters()` are the public functions.
They sort by campaign UUID, metric name, and horizon. Grouping never crosses a
campaign boundary; all input records must belong to exactly one organization.

### Dependency decision

AI-03 deliberately and narrowly departs from AI-01's standard-library/Decimal
implementation. The declared bounded compatibility ranges are `numpy>=2.5,<3.0`
for the numerical arrays passed to sklearn, `pandas>=3.0,<4.0` for the dev-only
tabular CSV evidence export, and `scikit-learn>=1.9,<2.0` for
`RandomForestRegressor`. These ranges are anchored to current stable releases
and support the backend's Python `>=3.12,<3.13` requirement.

They match this repository's existing bounded-range dependency convention; AI-03
does not add exact `==` pins or a new lockfile because `apps/backend` has none.
This is an approved exception scoped to forecasting only: it does not alter
AI-01 and other AI modules must separately justify using these packages. The
team accepts the larger Docker image and longer CI installation as the reasonable
runtime/build tradeoff for the specified Random Forest model and evidence export.

## 5. Inputs

| Input | Type | Required | Source | Semantics |
|---|---|---:|---|---|
| `features` | `list[FeatureRecord]` | yes | AI-01 | Already validated, organization-scoped campaign-day observations. |
| `horizons` | positive integer tuple | no | caller | Defaults to `(7, 14, 30)`. |
| `holdout_points` | positive integer | no | caller | Defaults to 7 observed targets. |

Supported v1 metrics are `spend`, `conversions`, and `roas`. Impression/click and
derived CTR/CPC/CPA metrics are deliberately excluded: this task's approved
forecast contract and evaluation set are limited to business outcome metrics.
An unavailable `roas` is not an observed point for the ROAS series.

## 6. Outputs

| Output | Nullable fields | Consumer | Description |
|---|---|---|---|
| `ForecastRecord` | `value`, `ci_lower`, `ci_upper` | Later API/AI-06 work | `organization_id`, `campaign_id`, metric, target date, horizon, chosen model, and the last usable observation date. |
| `ForecastEvaluation` | `mae`, `rmse`, `mape` | Model comparison / later orchestration | One organization/campaign/metric/model/horizon error summary. |

`ModelUsed` values are `moving_average`, `linear_regression`, `random_forest`, and
`insufficient_history`. The in-memory forecast contract permits null values for
the explicit degraded state. This intentionally differs from the canonical
persisted `forecasts.value`, which is non-null; persistence is deferred and no
database contract is changed here.

## 7. Rules and Semantics

### Gap handling and divergence from AI-01

**GAP-HANDLING RULE:** gaps are never interpolated or fabricated. Each model uses
its last N observed points, skips unavailable/no-data dates, and gates on an
observed-point count. Linear regression and Random Forest still use each point's
real calendar-day offset from the first selected observation. This intentionally
diverges from AI-01's complete-calendar-window rolling rule: requiring a complete
window would starve the 21-observation forest of usable real-world gapped series.

### Models and fallback

| Model | Minimum observed history | Rule | Interval |
|---|---:|---|---|
| Random Forest | 21 | `RandomForestRegressor`, 100 trees, `random_state=42`, `n_jobs=1`; one calendar-offset feature | Tree prediction 2.5th–97.5th percentiles, widened if necessary to contain the point estimate. |
| Linear Regression | 14 | Closed-form OLS for `(calendar offset, value)` | Residual population standard deviation × 1.96. |
| Moving Average | 7 | Arithmetic mean of the last seven observations | Window residual population standard deviation × 1.96. |

The first eligible tier wins: Random Forest → Linear Regression → Moving Average
→ an `insufficient_history` record with null forecast and interval. Normal lack
of history is never an exception or a dropped row. Flat series have a defined
zero-width interval. Every non-degraded projection enforces
`ci_lower <= value <= ci_upper`.

Moving average is `mean(y_i)`. OLS is `y = intercept + slope*x`, where
`slope = Σ((x_i-x̄)(y_i-ȳ)) / Σ((x_i-x̄)^2)`. Random Forest intervals are the
fixed tree-prediction percentiles above. Backtests calculate
`MAE = mean(|prediction - actual|)`, `RMSE = sqrt(mean(error²))`, and
`MAPE = mean(|prediction-actual| / |actual|)` over non-zero actuals; MAPE is
`None` when every comparable actual is zero.

Backtesting uses rolling origins among the last K observed targets. A target is
included only if there is an actual observation exactly the requested calendar
horizon after its origin. Each model is refit on observations through that
origin. Origins must meet the 21-observation shared threshold, so all models are
scored on exactly the same target dates and are objectively comparable. Metrics
are `None` when no comparable targets exist.

### Precision boundary

AI-03 uses `Decimal` outside the Random Forest implementation, preserving AI-01's
pinned Decimal context. sklearn/numpy accept floats, so only `RandomForestForecaster`
converts Decimal values to float internally and converts results immediately back
using `Decimal(str(float))`. This is a scoped ML-boundary exception.

## 8. Public Interfaces

- `generate_forecasts(features, horizons=(7, 14, 30)) -> list[ForecastRecord]`
  validates local input shape, then returns deterministic projections.
- `evaluate_forecasters(features, holdout_points=7) -> list[ForecastEvaluation]`
  performs deterministic, comparable rolling-origin backtesting.
- `ForecastDataError` indicates malformed input such as mixed organizations or
  duplicate campaign/date rows; it does not represent normal short history.

## 9. Data Ownership

### Reads

- `FeatureRecord` passed by the caller, normally created by AI-01.
- The evidence script reads `daily_metrics` only through AI-01's
  `DatabaseDataLoader`.

### Writes

- None in the shipped package. The dev-only script writes local CSV/JSON evidence
  under gitignored `artifacts/ai03/`.

### Must Never Read

- Raw provider payloads, credentials, or a new forecasting-specific database path.

### Must Never Write

- `forecasts`, `model_runs`, Worker jobs, migrations, or any AI/data table.

## 10. Security

Forecasting adds no query path. It preserves the organization and campaign IDs
already scoped by AI-01, rejects mixed-organization input, and groups separately
by campaign so forecast/evaluation history cannot leak across campaigns.

## 11. Error and Edge-Case Behavior

| Case | Expected behavior |
|---|---|
| Empty input | Empty deterministic output. |
| Mixed organization / duplicate campaign-date / unsupported malformed value | `ForecastDataError`. |
| Insufficient history | Degraded `ForecastRecord`; evaluation errors are `None` where no comparable targets exist. |
| Date gap | Skipped; never interpolated. |
| Undefined ROAS | Not an observed ROAS point. |
| Flat values | Valid zero-width CI. |
| Zero actual in MAPE | Excluded; all-zero MAPE becomes `None`. |

## 12. Testing

Unit coverage includes exact moving-average/OLS values, forest repeatability and
CI sanity, every fallback tier, gaps, flat histories, MAPE missing semantics,
campaign/organization isolation, backtest MAE/RMSE, and entrypoint ordering.
The integration test uses the seeded Nour Fashion Co. data through AI-01's
read-only database loader and never persists forecasts.

## 13. Verification

Executed on 2026-09-05 with Python 3.12.10 after the CI-equivalent editable
installation command `python -m pip install -e ".[dev]"`. The Windows console
wrappers were not on `PATH`, so the same tools ran through Python modules.

- `python -m ruff check .`: **PASS** — all checks passed.
- `python -m ruff format --check .`: **PASS** — 140 files already formatted.
- `python -m mypy src`: **PASS** — no issues in 81 source files; the repository
  still emits pre-existing configuration warnings for `jose`/`passlib` overrides.
- `python -m pytest tests/unit/ai/test_forecasting.py -v`: **PASS** — 14 passed
  in 18.41 seconds (two third-party deprecation warnings).
- `python -m pytest tests/unit -v`: **PASS** — 97 passed in 23.49 seconds.
- Non-database suite: **PASS** — 140 passed, 9 skipped, in 23.74 seconds.
- `tests/integration/ai/test_database_loader.py` (pre-existing AI-01) and
  `tests/integration/ai/test_forecasting_integration.py`: **NOT RUN — PostgreSQL
  unavailable locally (DB infra owned by other team members, out of scope for
  AI-03).** `localhost:5434` refused TCP connections.

## 14. Known Limitations

- No DB persistence or Worker wiring; both are deferred to AI-06.
- The forest uses only one time-offset feature, not AI-01's richer features.
- Forest quality on the seeded 90-day dataset must be judged from executed
  evidence, not presumed superior to the simpler models. Backtest artifacts are
  **NOT RUN — no Python runtime is available in this workspace**.
- Gap behavior intentionally differs from AI-01 as documented above.

## 15. Follow-Up Tasks

### Verification addendum

The real non-database verification results are recorded in section 13. The Nour
evidence export and both AI database integration tests remain **NOT RUN —
PostgreSQL unavailable locally (DB infra owned by other team members, out of
scope for AI-03)**. No database infrastructure was installed or configured.

- AI-06 — persist approved output and orchestrate runs without moving forecast
  mathematics into Worker code.
- Future approved forecasting work — evaluate richer, explicitly justified
  AI-01 feature inputs for Random Forest.

## 16. References and Evidence

- Run from an installed backend environment with `DATABASE_URL` pointing at a
  migrated seeded database: `python scripts/ai03_evidence.py`.
- The command writes `artifacts/ai03/forecasts.csv`, `evaluations.csv`, and JSON
  equivalents. The directory is intentionally gitignored.
- Canonical persisted-table reference:
  [`tests/contracts/canonical.json`](../../tests/contracts/canonical.json).
