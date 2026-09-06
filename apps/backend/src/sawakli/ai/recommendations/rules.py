"""The four AI-04 diagnosis rules.

Each rule is a pure function over one campaign's ``FeatureRecord`` history (AI-01's real output,
sorted ascending by date) and returns a ``RuleTrigger`` or ``None``. Every rule is self-sufficient
against feature data alone — none of them require an ``AnomalySignal`` or ``ForecastPoint`` to
fire. Matching anomaly/forecast data (when present) is attached afterwards by ``engine.py`` and
only strengthens confidence/severity or enriches evidence text; its absence never breaks a rule.

Rule boundary: this module only decides *whether* a rule fires and *how strong* the signal is. It
does not decide the human-readable wording (``explain.py``) and does not persist anything
(Pipeline Orchestrator / AI-06 — see ``docs/ai/AI-04-recommendation-engine.md`` Section 2).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sawakli.ai.features import FeatureRecord, safe_divide
from sawakli.ai.forecasting import ForecastRecord

from .schemas import AnomalyDirection, AnomalySignal
from .thresholds import (
    CONVERSION_DROP_RELATIVE_THRESHOLD,
    CONVERSION_DROP_SEVERE_MULTIPLIER,
    CPA_BASELINE_MIN_DAYS,
    CPA_BASELINE_WINDOW_DAYS,
    CPA_SPIKE_RELATIVE_THRESHOLD,
    CPA_SPIKE_SEVERE_MULTIPLIER,
    CTR_DROP_RELATIVE_THRESHOLD,
    CTR_DROP_SEVERE_MULTIPLIER,
    SPEND_WASTE_BASELINE_MIN_DAYS,
    SPEND_WASTE_BASELINE_WINDOW_DAYS,
    SPEND_WASTE_ROAS_THRESHOLD,
    SPEND_WASTE_SEVERE_ROAS,
)


def _decimal_sum(values: Sequence[Decimal]) -> Decimal:
    """Deterministic sum of already-validated ``Decimal`` values.

    AI-01's own ``decimal_sum`` (pinned Decimal context, ``ai/features/metrics.py``) is not part of
    its declared public contract (``ai/features/__init__.py`` only exports ``safe_divide``), so
    this rule module defines its own trivial equivalent rather than reaching into AI-01's private
    internals across the package boundary.
    """

    total = Decimal(0)
    for value in values:
        total += value
    return total


@dataclass(frozen=True, slots=True)
class RuleTrigger:
    """One rule's positive result for one campaign, before wording or scoring is attached."""

    rule_id: str
    organization_id: UUID
    campaign_id: UUID
    campaign_name: str
    metric_name: str
    direction: AnomalyDirection
    observed_value: Decimal
    reference_value: Decimal
    relative_change: Decimal
    severe: bool
    matched_anomaly: AnomalySignal | None = None
    matched_forecast: ForecastRecord | None = None
    context: Mapping[str, Decimal] = field(default_factory=dict)


def evaluate_ctr_drop(history: Sequence[FeatureRecord]) -> RuleTrigger | None:
    """Today's CTR fell at least ``CTR_DROP_RELATIVE_THRESHOLD`` below its own 7-day rolling CTR."""

    latest = history[-1]
    if latest.ctr is None or latest.rolling_ctr_7d is None or latest.rolling_ctr_7d == 0:
        return None
    drop = safe_divide(latest.rolling_ctr_7d - latest.ctr, latest.rolling_ctr_7d)
    if drop is None or drop <= CTR_DROP_RELATIVE_THRESHOLD:
        return None
    return RuleTrigger(
        rule_id="ctr_drop",
        organization_id=latest.organization_id,
        campaign_id=latest.campaign_id,
        campaign_name=latest.campaign_name,
        metric_name="ctr",
        direction="below",
        observed_value=latest.ctr,
        reference_value=latest.rolling_ctr_7d,
        relative_change=drop,
        severe=drop >= CTR_DROP_RELATIVE_THRESHOLD * CTR_DROP_SEVERE_MULTIPLIER,
    )


def evaluate_cpa_spike(history: Sequence[FeatureRecord]) -> RuleTrigger | None:
    """Today's CPA is at least ``CPA_SPIKE_RELATIVE_THRESHOLD`` above its own trailing mean CPA.

    The trailing mean is computed here (a plain arithmetic mean of daily CPA values over the prior
    ``CPA_BASELINE_WINDOW_DAYS`` days), because AI-01 does not expose a ``rolling_cpa`` field.
    """

    latest = history[-1]
    if latest.cpa is None:
        return None
    baseline_window = history[-(CPA_BASELINE_WINDOW_DAYS + 1) : -1]
    baseline_values = [record.cpa for record in baseline_window if record.cpa is not None]
    if len(baseline_values) < CPA_BASELINE_MIN_DAYS:
        return None
    baseline_mean = safe_divide(_decimal_sum(baseline_values), len(baseline_values))
    if baseline_mean is None or baseline_mean == 0:
        return None
    spike = safe_divide(latest.cpa - baseline_mean, baseline_mean)
    if spike is None or spike <= CPA_SPIKE_RELATIVE_THRESHOLD:
        return None
    return RuleTrigger(
        rule_id="cpa_spike",
        organization_id=latest.organization_id,
        campaign_id=latest.campaign_id,
        campaign_name=latest.campaign_name,
        metric_name="cpa",
        direction="above",
        observed_value=latest.cpa,
        reference_value=baseline_mean,
        relative_change=spike,
        severe=spike >= CPA_SPIKE_RELATIVE_THRESHOLD * CPA_SPIKE_SEVERE_MULTIPLIER,
    )


def evaluate_spend_waste(history: Sequence[FeatureRecord]) -> RuleTrigger | None:
    """The campaign's trailing mean ROAS is below ``SPEND_WASTE_ROAS_THRESHOLD`` (losing money).

    An absolute threshold, not a change-detection threshold: a campaign can be persistently
    wasteful without anything having changed, so this rule intentionally does not require a
    matching anomaly to fire (INT-01 4.2 — ``source_anomaly_id`` is nullable for this reason).
    """

    latest = history[-1]
    window = history[-SPEND_WASTE_BASELINE_WINDOW_DAYS:]
    roas_values = [record.roas for record in window if record.roas is not None]
    if len(roas_values) < SPEND_WASTE_BASELINE_MIN_DAYS:
        return None
    mean_roas = safe_divide(_decimal_sum(roas_values), len(roas_values))
    if mean_roas is None or mean_roas >= SPEND_WASTE_ROAS_THRESHOLD:
        return None
    shortfall = safe_divide(SPEND_WASTE_ROAS_THRESHOLD - mean_roas, SPEND_WASTE_ROAS_THRESHOLD)
    if shortfall is None:
        return None
    return RuleTrigger(
        rule_id="spend_waste",
        organization_id=latest.organization_id,
        campaign_id=latest.campaign_id,
        campaign_name=latest.campaign_name,
        metric_name="roas",
        direction="below",
        observed_value=mean_roas,
        reference_value=SPEND_WASTE_ROAS_THRESHOLD,
        relative_change=shortfall,
        severe=mean_roas <= SPEND_WASTE_SEVERE_ROAS,
    )


def evaluate_conversion_drop(history: Sequence[FeatureRecord]) -> RuleTrigger | None:
    """AI-01's own ``conversion_trend`` shows a day-over-day drop of at least the threshold.

    Uses an already-computed AI-01 field directly rather than a new baseline — the most tightly
    coupled to real, existing data of the four rules. When available, ``bounce_rate`` is attached
    as context so the explanation can point at a possible landing-page cause (see PROD-01's Nour
    Fashion Co. demo story, which pairs a conversion issue with a bounce-rate finding).
    """

    latest = history[-1]
    trend = latest.conversion_trend
    if trend is None or trend > -CONVERSION_DROP_RELATIVE_THRESHOLD:
        return None
    # latest.conversion_trend being non-None means AI-01 had an unbroken previous-day record
    # *when it computed that field*. That is not automatically true of history[-2] *here* — this
    # function only sees whatever slice of history its caller passed in. Re-check length and date
    # adjacency directly (rather than trusting the field's mere presence, or indexing blindly) so
    # a caller that forwards a short, gapped, or filtered history can never crash or produce a
    # mislabeled "previous conversions" number in the evidence text.
    if len(history) < 2 or history[-2].date != latest.date - timedelta(days=1):
        return None
    previous = history[-2]
    magnitude = -trend
    context: dict[str, Decimal] = {}
    if latest.bounce_rate is not None:
        context["bounce_rate"] = latest.bounce_rate
    return RuleTrigger(
        rule_id="conversion_drop",
        organization_id=latest.organization_id,
        campaign_id=latest.campaign_id,
        campaign_name=latest.campaign_name,
        metric_name="conversions",
        direction="below",
        observed_value=Decimal(latest.conversions),
        reference_value=Decimal(previous.conversions),
        relative_change=magnitude,
        severe=magnitude >= CONVERSION_DROP_RELATIVE_THRESHOLD * CONVERSION_DROP_SEVERE_MULTIPLIER,
        context=context,
    )


#: Fixed, deterministic evaluation order — also the order recommendations are emitted per campaign.
RULES = (
    evaluate_ctr_drop,
    evaluate_cpa_spike,
    evaluate_spend_waste,
    evaluate_conversion_drop,
)
