"""AI-04 public entry point: turns features (+ optional anomalies/forecasts) into recommendations.

Scope boundary (see ``docs/ai/AI-04-recommendation-engine.md`` Section 2): this module is pure
computation. It never opens a database session and never persists anything — mirroring AI-01,
which produces ``FeatureRecord`` objects without writing them anywhere. Turning the returned
``Recommendation`` objects into ``recommendations`` table rows (minting ``id``, ``model_run_id``,
and the default ``status``) is Pipeline Orchestrator (AI-06) work.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace
from uuid import UUID

from sawakli.ai.features import FeatureRecord
from sawakli.ai.forecasting import ForecastRecord, ModelUsed

from .explain import build_evidence
from .rules import RULES, RuleTrigger
from .schemas import AnomalySignal, Recommendation, RecommendationDataError
from .scoring import RISK_BY_RULE, score_trigger

_AnomalyKey = tuple[UUID, str]
_ForecastKey = tuple[UUID, str]


def generate_recommendations(
    features: Iterable[FeatureRecord],
    anomalies: Iterable[AnomalySignal] = (),
    forecasts: Iterable[ForecastRecord] = (),
) -> tuple[Recommendation, ...]:
    """Evaluate all four rules for every campaign present in ``features``.

    ``anomalies`` and ``forecasts`` are optional in every sense that matters: an empty tuple (the
    only thing available before AI-02 exists) produces recommendations driven by feature data
    alone. When present, an anomaly or forecast for a campaign *not* in ``features`` is ignored —
    that is a normal "different scope of this pipeline run" situation, not an error. An anomaly or
    forecast for a campaign that *is* in ``features`` but tagged with a different
    ``organization_id`` is an organization-isolation violation and raises immediately.

    A ``ForecastRecord`` with ``model_used == ModelUsed.INSUFFICIENT_HISTORY`` or a ``None``
    ``value`` (AI-03's degraded-forecast representation — see ``docs/ai/AI-03-forecasting.md``)
    carries nothing usable for evidence text and is never matched. AI-03 only ever forecasts
    ``spend``, ``conversions``, and ``roas`` (never ``ctr`` or ``cpa``), so the ``ctr_drop`` and
    ``cpa_spike`` rules can never receive real forecast enrichment — only ``spend_waste`` and
    ``conversion_drop`` can.

    Recommendations are evaluated only against each campaign's most recent (latest-dated) record;
    earlier records are used only as history for baselines and rolling context, never diagnosed
    on their own. Output order is deterministic: campaigns ordered by UUID, rules evaluated in the
    fixed order defined in ``rules.RULES`` within each campaign.

    Correlation for downstream consumers (e.g. AI-05's action simulator, whose output has a
    ``NOT NULL`` FK back to a recommendation, but which runs before any DB ``id`` is minted):
    every ``Recommendation`` in one call's return value has a unique ``(campaign_id, rule_id)``
    pair, since each rule fires at most once per campaign per call. Use that pair, not list
    position, to know which simulation batch belongs to which recommendation.
    """

    features_by_campaign = _group_features(features)
    anomalies_by_key = _index_anomalies(anomalies, features_by_campaign)
    forecasts_by_key = _index_forecasts(forecasts, features_by_campaign)

    results: list[Recommendation] = []
    for campaign_id in sorted(features_by_campaign, key=lambda value: value.int):
        history = sorted(features_by_campaign[campaign_id], key=lambda record: record.date)
        for rule in RULES:
            trigger = rule(history)
            if trigger is None:
                continue
            trigger = _attach_signals(trigger, anomalies_by_key, forecasts_by_key)
            results.append(_to_recommendation(trigger))
    return tuple(results)


def _group_features(features: Iterable[FeatureRecord]) -> dict[UUID, list[FeatureRecord]]:
    grouped: dict[UUID, list[FeatureRecord]] = defaultdict(list)
    org_by_campaign: dict[UUID, UUID] = {}
    for record in features:
        expected_org = org_by_campaign.setdefault(record.campaign_id, record.organization_id)
        if expected_org != record.organization_id:
            raise RecommendationDataError(
                f"campaign_id={record.campaign_id} appears under multiple organizations"
            )
        grouped[record.campaign_id].append(record)
    return grouped


def _index_anomalies(
    anomalies: Iterable[AnomalySignal],
    features_by_campaign: Mapping[UUID, list[FeatureRecord]],
) -> dict[_AnomalyKey, AnomalySignal]:
    indexed: dict[_AnomalyKey, AnomalySignal] = {}
    for signal in anomalies:
        campaign_features = features_by_campaign.get(signal.campaign_id)
        if campaign_features is None:
            continue  # out of scope for this run — not an error, see docstring above.
        if campaign_features[0].organization_id != signal.organization_id:
            raise RecommendationDataError(
                f"anomaly for campaign_id={signal.campaign_id} has organization_id="
                f"{signal.organization_id}, expected {campaign_features[0].organization_id}"
            )
        indexed[(signal.campaign_id, signal.metric_name)] = signal
    return indexed


def _index_forecasts(
    forecasts: Iterable[ForecastRecord],
    features_by_campaign: Mapping[UUID, list[FeatureRecord]],
) -> dict[_ForecastKey, ForecastRecord]:
    nearest: dict[_ForecastKey, ForecastRecord] = {}
    for point in forecasts:
        campaign_features = features_by_campaign.get(point.campaign_id)
        if campaign_features is None:
            continue
        if campaign_features[0].organization_id != point.organization_id:
            raise RecommendationDataError(
                f"forecast for campaign_id={point.campaign_id} has organization_id="
                f"{point.organization_id}, expected {campaign_features[0].organization_id}"
            )
        if point.model_used == ModelUsed.INSUFFICIENT_HISTORY or point.value is None:
            continue  # degraded forecast — nothing usable to attach as evidence.
        key = (point.campaign_id, point.metric_name)
        current = nearest.get(key)
        if current is None or point.forecast_date < current.forecast_date:
            nearest[key] = point
    return nearest


def _attach_signals(
    trigger: RuleTrigger,
    anomalies_by_key: Mapping[_AnomalyKey, AnomalySignal],
    forecasts_by_key: Mapping[_ForecastKey, ForecastRecord],
) -> RuleTrigger:
    matched_anomaly = anomalies_by_key.get((trigger.campaign_id, trigger.metric_name))
    if matched_anomaly is not None and matched_anomaly.direction != trigger.direction:
        matched_anomaly = None  # a same-metric anomaly in the opposite direction does not confirm.
    matched_forecast = forecasts_by_key.get((trigger.campaign_id, trigger.metric_name))
    return replace(trigger, matched_anomaly=matched_anomaly, matched_forecast=matched_forecast)


def _to_recommendation(trigger: RuleTrigger) -> Recommendation:
    problem, suggested_action, evidence = build_evidence(trigger)
    confidence_score, severity = score_trigger(trigger)
    return Recommendation(
        organization_id=trigger.organization_id,
        campaign_id=trigger.campaign_id,
        source_anomaly_id=trigger.matched_anomaly.id if trigger.matched_anomaly else None,
        problem=problem,
        evidence=evidence,
        suggested_action=suggested_action,
        confidence_score=confidence_score,
        risk_rating=RISK_BY_RULE[trigger.rule_id],
        severity=severity,
        rule_id=trigger.rule_id,
    )
