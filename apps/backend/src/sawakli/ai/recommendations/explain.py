"""Template-based explainability formatter.

This is deliberately *not* natural-language generation in the modern sense — no model, no
inference. Each ``rule_id`` maps to a fixed template with named placeholders; this module computes
the values and fills them in. This matches the AI Layer design document's own description of Task
1.8 ("Template-based NLG: maps rule id to business-language templates with variable injection") and
the repository's ``AGENTS.md`` model philosophy (interpretable, testable, no hosted-model
dependency for the current MVP).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .rules import RuleTrigger


def _as_percent(value: Decimal, places: str = "0.1") -> str:
    """Render a ratio (e.g. ``Decimal("0.032")``) as ``"3.2%"``."""

    return f"{(value * 100).quantize(Decimal(places), rounding=ROUND_HALF_UP)}%"


def _as_number(value: Decimal, places: str = "0.01") -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _problem_and_action(trigger: RuleTrigger) -> tuple[str, str]:
    name = trigger.campaign_name
    if trigger.rule_id == "ctr_drop":
        return (
            f"Click-through rate has dropped for {name}",
            f"Refresh the ad creative and review audience targeting for {name}.",
        )
    if trigger.rule_id == "cpa_spike":
        return (
            f"Cost per acquisition has spiked for {name}",
            f"Reduce budget for {name} and review targeting until CPA recovers.",
        )
    if trigger.rule_id == "spend_waste":
        return (
            f"{name} is spending more than it returns",
            f"Reduce budget for {name}; current spend is not generating proportional revenue.",
        )
    if trigger.rule_id == "conversion_drop":
        return (
            f"Conversions have dropped for {name} despite similar traffic",
            f"Review the landing page and checkout flow for {name}.",
        )
    raise ValueError(f"no explanation template for rule_id={trigger.rule_id!r}")  # pragma: no cover


def _core_evidence(trigger: RuleTrigger) -> tuple[str, ...]:
    if trigger.rule_id == "ctr_drop":
        reference = _as_percent(trigger.reference_value)
        drop = _as_percent(trigger.relative_change)
        return (
            f"CTR is {_as_percent(trigger.observed_value)}, down from a 7-day average of "
            f"{reference} ({drop} drop).",
        )
    if trigger.rule_id == "cpa_spike":
        return (
            f"CPA is {_as_number(trigger.observed_value)}, up from a "
            f"{_as_number(trigger.reference_value)} trailing average "
            f"({_as_percent(trigger.relative_change)} increase).",
        )
    if trigger.rule_id == "spend_waste":
        return (
            f"Average ROAS over the recent period is {_as_number(trigger.observed_value)}x, "
            f"below the {_as_number(trigger.reference_value)}x break-even line.",
        )
    if trigger.rule_id == "conversion_drop":
        previous_count = int(trigger.reference_value)
        drop = _as_percent(trigger.relative_change)
        evidence: tuple[str, ...] = (
            f"Conversions fell to {int(trigger.observed_value)} from {previous_count} the "
            f"previous day ({drop} drop).",
        )
        bounce_rate = trigger.context.get("bounce_rate")
        if bounce_rate is not None:
            evidence += (
                f"Landing page bounce rate is {_as_percent(bounce_rate)}, "
                "suggesting the issue may be past the click, not the ad itself.",
            )
        return evidence
    raise ValueError(f"no explanation template for rule_id={trigger.rule_id!r}")  # pragma: no cover


def build_evidence(trigger: RuleTrigger) -> tuple[str, str, tuple[str, ...]]:
    """Return ``(problem, suggested_action, evidence)`` for one triggered rule.

    ``evidence`` always starts with the rule's own core evidence line(s), then appends an
    anomaly-confirmation line and a forecast-projection line only when those inputs were actually
    matched — their absence never removes information, it just means less to say.
    """

    problem, suggested_action = _problem_and_action(trigger)
    evidence = list(_core_evidence(trigger))

    if trigger.matched_anomaly is not None:
        evidence.append(
            f"Confirmed by anomaly detection (severity: {trigger.matched_anomaly.severity})."
        )
    forecast = trigger.matched_forecast
    if forecast is not None and forecast.value is not None:
        evidence.append(
            f"Forecast projects {trigger.metric_name} of {_as_number(forecast.value)} in "
            f"{forecast.horizon_days} days ({forecast.forecast_date.isoformat()}, "
            f"{forecast.model_used.value} model) if nothing changes."
        )

    return problem, suggested_action, tuple(evidence)
