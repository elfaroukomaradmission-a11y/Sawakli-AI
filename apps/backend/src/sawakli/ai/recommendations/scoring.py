"""Shared confidence/severity scoring and risk-rating mapping for all four rules.

Kept in one small module, deliberately independent of rule-specific logic, so the whole scoring
formula for every recommendation can be read (and retuned) in one place. See ``thresholds.py`` for
the constants and their rationale.
"""

from __future__ import annotations

from decimal import Decimal

from .rules import RuleTrigger
from .schemas import RiskRating
from .thresholds import (
    CONFIDENCE_ANOMALY_BONUS,
    CONFIDENCE_BASE,
    CONFIDENCE_CEILING,
    CONFIDENCE_FLOOR,
    CONFIDENCE_MAGNITUDE_BONUS_CAP,
    SEVERITY_BASE,
    SEVERITY_CEILING,
    SEVERITY_FLOOR,
    SEVERITY_HIGH_ANOMALY_BONUS,
    SEVERITY_SEVERE_MAGNITUDE_BONUS,
)

#: Risk reflects the downside of the *suggested action*, not the severity of the problem.
#: ctr_drop and conversion_drop suggest non-budget actions (creative refresh, landing-page
#: review) that are low-risk to try. cpa_spike and spend_waste suggest cutting budget, which has a
#: real revenue downside if the diagnosis turns out to be wrong.
RISK_BY_RULE: dict[str, RiskRating] = {
    "ctr_drop": "low",
    "cpa_spike": "medium",
    "spend_waste": "medium",
    "conversion_drop": "low",
}


def score_trigger(trigger: RuleTrigger) -> tuple[Decimal, int]:
    """Return ``(confidence_score, severity)`` for a triggered rule.

    confidence_score (0-1) and severity (1-5) start from the same fixed base and pick up:
      - an anomaly bonus when a matching, direction-consistent ``AnomalySignal`` confirms the
        rule's own feature-based judgement (statistical + business agreement is more trustworthy
        than either alone);
      - a magnitude bonus when the rule's own ``severe`` flag is set (how far past its threshold
        the observed value fell, per-rule definition — see each rule in ``rules.py``).
    Both are clamped to their contract range (INT-01 4.3) so a future retune can never produce an
    out-of-range value.
    """

    confidence = CONFIDENCE_BASE
    severity = SEVERITY_BASE

    if trigger.matched_anomaly is not None:
        confidence += CONFIDENCE_ANOMALY_BONUS
        if trigger.matched_anomaly.severity == "high":
            severity += SEVERITY_HIGH_ANOMALY_BONUS

    if trigger.severe:
        confidence += CONFIDENCE_MAGNITUDE_BONUS_CAP
        severity += SEVERITY_SEVERE_MAGNITUDE_BONUS

    confidence = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, confidence))
    severity = max(SEVERITY_FLOOR, min(SEVERITY_CEILING, severity))
    return confidence, severity
