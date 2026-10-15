# AI-02 reference benchmark v1

## Purpose and provenance

On 15 October 2026 the project lead requested fixing the missing AI-02 evaluation
evidence and then merging PR #19, with human approval treated as satisfied.
The original DATA-02 generator and dated labels remain unavailable. This document
defines a **new reference benchmark**, not recovered or retrospectively inferred
labels for the historical 360-row Nour migration. The historical seed is unchanged.

Source: `apps/backend/tests/fixtures/ai02_benchmark.py`. Labels are defined by the
generator's intervention schedule, independently of predictions. The generator,
configuration and evaluation policy are fixed before its first detector run.
This benchmark supports bounded synthetic acceptance of the standalone detector;
it does not establish historical Nour accuracy, generalization, or full demo E2E.

## Fixed dataset and evaluation policy

- Version `ai02-reference-v1`; development seed `20261015`, reserved validation
  seed `20261016`; 90 calendar days from 1 January 2026 for each seed. The second
  seed was reserved before its first scoring run; the implementation was frozen
  before that run. It was not used to select a threshold or adjust the detector.
- 60 campaigns across three explicitly identified organizations, on Meta/Google.
- 30 wholly clean campaigns, and 30 campaigns with one injected event each.
- Ten spend-waste, ten CTR-drop, and ten positive-improvement events. Event starts
  vary across days 35–69 and durations are 3, 5 or 7 days. Identities and inclusive
  dates are exported as the ground-truth event manifest.
- Clean baselines vary by campaign scale, CTR, ROAS, weekly traffic and random
  day-to-day variation. They are not repeated constant-history copies.
- Every non-intervention campaign-day is explicitly clean, including early history
  and recovery dates. There are no unlabeled days, post-hoc warm-up exclusions,
  detector-derived labels or date tolerances.
- A flag means `score >= 0.80`, the existing **critical** severity boundary. This
  is a declared conservative benchmark operating point, not the prior fixture's
  diagnostic `0.40` and not a new production/API alert policy. Ensemble weights
  and severity boundaries remain unchanged. ARCH-03 must expose the chosen alert
  policy explicitly rather than treating any nonzero score as an alert.
- An event is detected only if a flag lies inside its inclusive interval. One flag
  cannot earn multiple matches because each campaign has one event.
- Event recall = detected events / 30. Day recall = flagged intervention days /
  all intervention days. Both must reach 80%.
- Clean-day FPR includes all explicitly clean rows, including clean periods in
  event campaigns. Clean-campaign FPR = wholly clean campaigns with **any** flag /
  30. Both must be at most 5%. Report integer numerators and denominators.
- Run real AI-01 engineering and the unmodified AI-02 detector on the full batch.
  The forest is retrospective; this is not causal online or held-out evaluation.

## Scope limitations

The three controlled event families exercise abnormal changes. Constant chronic
underperformance and the product's pause recommendation are not measured by this
relative-change benchmark. They remain product/integration acceptance work; a
low constant ROAS must not be relabeled as a sudden-change event to make recall
look better. Model calibration on real campaigns and an independently labeled
historical Nour run remain follow-ups, not claims made by this benchmark.

## Scoring correction

The original `106dde5` implementation failed the development benchmark: all 30
events were detected, but 14/30 clean campaigns had at least one critical flag.
The standalone run had 93/5,248 false-positive clean days. These failures were
retained; labels, scheduled interventions and the `0.80` threshold were not changed.

Inspection showed two sources of saturation: zero/near-zero historical spread
could turn tiny metric movement into a contribution of one, and each statistical
branch selected the maximum across 12 features. The fix gives level features a
minimum dispersion of 5% of their historical median (numerical floor `1e-12` at
zero), and relative trends a five-percentage-point minimum dispersion. The
statistical contribution is the mean of the two strongest feature contributions,
padding absent evidence with zero. Features are correlated; this is corroboration,
not a claim of independent statistical significance. See the exact formulas and
hand-calculable assertions in the [task document](../ai/AI-02-anomaly-detection.md).

A dispersion-floor-only intermediate candidate still failed (5/30 clean
campaigns flagged); it is not counted as accepted evidence. Neither intermediate
candidate was pushed. The final change preserves the forest, five-history gates,
ensemble weights and severity boundaries. It changes the statistical component
semantics and deliberately makes isolated single-feature changes less severe.

## Execution and evidence — 15 October 2026

From the repository root, in a Python 3.12 environment with `apps/backend[dev]`:

```bash
PYTHONPATH=apps/backend/src:apps/backend python scripts/ai02_benchmark.py --export-dir /tmp/ai02-dev
PYTHONPATH=apps/backend/src:apps/backend python scripts/ai02_benchmark.py --seed 20261016 --export-dir /tmp/ai02-validation
```

Both commands returned exit code zero and `status: PASS`. The exporter writes
`campaign_data.csv` and `labels.json` **before** detector execution, then writes
`results.json`. The label file includes every clean campaign-day, all event
identities and inclusive dates, no exclusions, the seed and the data digest. No
external credentials, SQL execution or database are needed.

| Measure | Development: 20261015 | Reserved validation: 20261016 |
|---|---|---|
| Facts | 5,400 | 5,400 |
| Event recall | 30/30 = 100% | 30/30 = 100% |
| Anomalous-day recall | 149/152 = 98.03% | 144/152 = 94.74% |
| Clean-day FPR | 62/5,248 = 1.18% | 59/5,248 = 1.12% |
| Clean-campaign FPR | 0/30 = 0% | 1/30 = 3.33% |
| Each event family | 10/10 detected | 10/10 detected |
| Gate result | PASS | PASS |

Exact data digests (SHA-256 of the generator's canonical fact serialization):

- Development: `4533a170f07e361b9e9fc77528aa56822fb07fae58a00e1aa1cd7828ee00ad62`.
- Validation: `414d813add890129a32d26af6ffe5ee444288eed261cc985de88dbd55ca66aee`.

Environment: CPython 3.12.14, NumPy 2.5.4, scikit-learn 1.9.1. These satisfy the
repository's declared ranges. CI replays both seeded datasets as assertions in
`tests/unit/ai/test_detector_benchmark.py`; digest assertions detect source drift.
The evaluation also rejects missing or duplicate results and verifies that an
event hit cannot conceal poor day recall or clean-campaign false positives.

The counts are small; one clean-campaign error is already 3.33%. Passing this
finite benchmark does not guarantee a population FPR below 5%. This is evidence
for the declared critical-alert operating point only. The prior `0.40` toy fixture
remains a separate regression, not evidence that medium-or-higher alerts meet
these quality targets.
