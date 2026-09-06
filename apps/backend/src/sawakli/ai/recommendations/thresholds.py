"""Explicit, documented thresholds for the four AI-04 rules.

No project document (proposal, GP_29_june, the AI Layer design docs, PROD-01, or INT-01) defines
numeric trigger thresholds for the recommendation engine — every reference is a single illustrative
sentence ("CPA rose 45% above its 14-day average"), not a locked contract value. Per
``docs/DOCUMENTATION_STANDARD.md`` Section 9 ("if an urgent temporary decision is necessary, it
still requires an explicit owner, written rationale, known limitation, and follow-up task"), the
values below are that decision, made explicit rather than buried inside rule logic.

Owner: AI-04 implementer. Rationale and limitations for each threshold are documented inline.
Follow-up: owner TBD — a dedicated tuning pass should revisit these once real AI-02/AI-03 output
exists on the seeded demo data. They are reasonable defaults, not values backtested against real
detector behavior, because no detector exists yet.
"""

from __future__ import annotations

from decimal import Decimal

# --- CTR drop rule -----------------------------------------------------------------------------
# Trigger: today's CTR is at least this fraction below the campaign's own rolling 7-day CTR
# (AI-01's ``rolling_ctr_7d``, a ratio of aggregated raw facts — see AI-01 completion report
# Section 6.1). 25% was chosen as a mid-point: small enough to catch a real creative-fatigue drop
# within the 90-day demo window, large enough that ordinary day-to-day noise should not fire it.
CTR_DROP_RELATIVE_THRESHOLD = Decimal("0.25")
# A drop at least this many times the trigger threshold (i.e. >= 50% below the rolling average)
# is treated as "severe" for scoring purposes — see CONFIDENCE_MAGNITUDE_BONUS_CAP below.
CTR_DROP_SEVERE_MULTIPLIER = Decimal("2.0")

# --- CPA spike rule ------------------------------------------------------------------------------
# Trigger: today's CPA is at least this fraction above the campaign's own trailing mean CPA.
# AI-01 does not expose a ``rolling_cpa`` field (only CTR/CPC have rolling variants), so this rule
# computes its own simple trailing mean directly from FeatureRecord.cpa over the window below,
# using AI-01's public ``safe_divide`` plus a small local sum helper (``rules._decimal_sum`` —
# AI-01's own ``decimal_sum`` is not part of its declared public contract, see that helper's
# docstring). This is a plain arithmetic mean of daily ratios, not a ratio of aggregates like
# AI-01's rolling CTR/CPC — a deliberately simpler choice, documented so it is not mistaken for
# the same rigor.
CPA_SPIKE_RELATIVE_THRESHOLD = Decimal("0.30")
CPA_SPIKE_SEVERE_MULTIPLIER = Decimal("2.0")
CPA_BASELINE_WINDOW_DAYS = 14
CPA_BASELINE_MIN_DAYS = 3  # fewer prior days than this: insufficient history, rule is skipped.

# --- Spend waste rule ----------------------------------------------------------------------------
# Trigger: the campaign's trailing mean ROAS is below this value, i.e. revenue is not even
# covering spend. This is an absolute business threshold, not a change-detection threshold — a
# campaign can be "wasteful" without anything having changed, which is why this rule does not
# require a matching anomaly to fire (see ``source_anomaly_id`` being nullable, INT-01 4.2).
SPEND_WASTE_ROAS_THRESHOLD = Decimal("1.0")
# A trailing mean ROAS at or below this absolute value is "severe" regardless of the 1.0 trigger
# line — e.g. 0.5 means the campaign is losing half of every pound spent, not just breaking even.
SPEND_WASTE_SEVERE_ROAS = Decimal("0.5")
SPEND_WASTE_BASELINE_WINDOW_DAYS = 7
SPEND_WASTE_BASELINE_MIN_DAYS = 3

# --- Conversion drop rule ------------------------------------------------------------------------
# Trigger: AI-01's own ``conversion_trend`` (day-over-day relative change) is at or below the
# negative of this value. Uses an already-computed AI-01 field directly rather than a new
# baseline, keeping this rule the most tightly coupled to real, existing data of the four.
CONVERSION_DROP_RELATIVE_THRESHOLD = Decimal("0.30")
CONVERSION_DROP_SEVERE_MULTIPLIER = Decimal("2.0")

# --- Scoring -------------------------------------------------------------------------------------
# confidence_score (0-1) and severity (1-5, INT-01 4.3 — distinct from anomalies.severity) share
# the same simple, documented heuristic across all four rules rather than a per-rule formula:
#   - a fixed base value;
#   - a bonus when a matching AnomalySignal confirms the same metric/direction statistically;
#   - a bonus scaled by how far the observed value is past the rule's threshold.
# This keeps scoring easy to explain to a reviewer and easy to retune in one place later.
CONFIDENCE_BASE = Decimal("0.55")
CONFIDENCE_ANOMALY_BONUS = Decimal("0.20")
CONFIDENCE_MAGNITUDE_BONUS_CAP = Decimal("0.15")
CONFIDENCE_FLOOR = Decimal("0.05")
CONFIDENCE_CEILING = Decimal("0.95")

SEVERITY_BASE = 3
SEVERITY_HIGH_ANOMALY_BONUS = 1
SEVERITY_SEVERE_MAGNITUDE_BONUS = 1  # observed value at least 2x past the threshold
SEVERITY_FLOOR = 1
SEVERITY_CEILING = 5
