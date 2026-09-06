from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from sawakli.ai.features import FeatureRecord, MetricRecord, engineer_features
from sawakli.ai.forecasting import ForecastRecord, ModelUsed
from sawakli.ai.recommendations import (
    AnomalySignal,
    Recommendation,
    RecommendationDataError,
    generate_recommendations,
)
from sawakli.ai.recommendations.explain import build_evidence
from sawakli.ai.recommendations.rules import RULES, RuleTrigger
from sawakli.ai.recommendations.scoring import score_trigger
from sawakli.ai.recommendations.thresholds import (
    CONFIDENCE_ANOMALY_BONUS,
    CONFIDENCE_BASE,
    CONFIDENCE_MAGNITUDE_BONUS_CAP,
    SEVERITY_BASE,
    SEVERITY_HIGH_ANOMALY_BONUS,
)

ORG = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORG = UUID("10000000-0000-0000-0000-000000000099")
CAMPAIGN_A = UUID("20000000-0000-0000-0000-000000000001")
CAMPAIGN_B = UUID("20000000-0000-0000-0000-000000000002")
START = date(2026, 1, 1)


def _metric(
    day: date,
    *,
    campaign_id: UUID = CAMPAIGN_A,
    campaign_name: str = "Campaign A",
    spend: str = "100",
    impressions: int = 1000,
    clicks: int = 50,
    conversions: int = 10,
    revenue: str = "300",
    sessions: int | None = None,
    bounces: int | None = None,
) -> MetricRecord:
    return MetricRecord(
        organization_id=ORG,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        platform="meta",
        date=day,
        spend=Decimal(spend),
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        revenue=Decimal(revenue),
        sessions=sessions,
        bounces=bounces,
    )


def _steady_history(days: int, **overrides: object) -> list[MetricRecord]:
    """``days`` identical, healthy campaign-day records: ctr=0.05, cpa=10, roas=3.0."""

    return [_metric(START + timedelta(days=i), **overrides) for i in range(days)]  # type: ignore[arg-type]


# ---------------------------------------------------------------------------------------------
# Each rule fires in isolation and does not cross-trigger the other three.
# ---------------------------------------------------------------------------------------------


def test_ctr_drop_fires_in_isolation() -> None:
    history = _steady_history(20)
    history.append(_metric(START + timedelta(days=20), clicks=15))  # ctr 0.05 -> 0.015
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert [r.rule_id for r in recs] == ["ctr_drop"]
    rec = recs[0]
    assert rec.campaign_id == CAMPAIGN_A
    assert rec.organization_id == ORG
    assert rec.source_anomaly_id is None
    assert rec.risk_rating == "low"
    assert "Click-through rate has dropped" in rec.problem


def test_cpa_spike_fires_in_isolation() -> None:
    history = _steady_history(20)
    history.append(_metric(START + timedelta(days=20), spend="200"))  # cpa 10 -> 20
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert [r.rule_id for r in recs] == ["cpa_spike"]
    assert recs[0].risk_rating == "medium"


def test_spend_waste_fires_when_trailing_roas_is_chronically_low() -> None:
    history = _steady_history(21, revenue="80")  # roas 0.8 every day, all 21 days
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert [r.rule_id for r in recs] == ["spend_waste"]
    assert recs[0].severity < 4  # 0.8 is below the 1.0 line but not below the 0.5 "severe" line


def test_spend_waste_severity_increases_when_roas_is_far_below_break_even() -> None:
    history = _steady_history(21, revenue="30")  # roas 0.3 every day: well past the severe line
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert [r.rule_id for r in recs] == ["spend_waste"]
    assert recs[0].severity == SEVERITY_BASE + 1


def test_spend_waste_does_not_fire_from_a_single_bad_day() -> None:
    history = _steady_history(20)
    history.append(_metric(START + timedelta(days=20), revenue="30"))  # one bad day only
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert "spend_waste" not in [r.rule_id for r in recs]


def test_conversion_drop_fires_without_spiking_cpa_or_roas() -> None:
    history = _steady_history(20)
    # Spend, conversions, and revenue all scale down together so CPA (spend/conversions) and
    # ROAS (revenue/spend) stay at their healthy baseline; only the conversion count itself drops.
    history.append(_metric(START + timedelta(days=20), spend="60", conversions=6, revenue="180"))
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert [r.rule_id for r in recs] == ["conversion_drop"]
    assert recs[0].risk_rating == "low"


def test_conversion_drop_evidence_mentions_bounce_rate_when_available() -> None:
    history = _steady_history(20, sessions=400, bounces=100)
    history.append(
        _metric(
            START + timedelta(days=20),
            spend="60",
            conversions=6,
            revenue="180",
            sessions=400,
            bounces=380,  # bounce rate spikes to 0.95 on the same day conversions drop
        )
    )
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert len(recs) == 1
    assert any("bounce rate" in line.lower() for line in recs[0].evidence)


def test_healthy_campaign_produces_no_recommendations() -> None:
    history = _steady_history(21)
    features = engineer_features(history)

    assert generate_recommendations(features) == ()


def test_empty_features_produce_no_recommendations() -> None:
    assert generate_recommendations([]) == ()


# ---------------------------------------------------------------------------------------------
# Multiple rules / multiple campaigns: deterministic ordering.
# ---------------------------------------------------------------------------------------------


def test_two_rules_on_one_campaign_are_ordered_per_RULES_tuple() -> None:
    history = _steady_history(20)
    # conversions drop 50% (fires conversion_drop) while spend stays flat, so CPA doubles too
    # (fires cpa_spike). RULES = (ctr_drop, cpa_spike, spend_waste, conversion_drop), so cpa_spike
    # must be reported before conversion_drop.
    history.append(_metric(START + timedelta(days=20), conversions=5))
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert [r.rule_id for r in recs] == ["cpa_spike", "conversion_drop"]


def test_campaigns_are_ordered_by_campaign_id_regardless_of_input_order() -> None:
    history_a = _steady_history(20, campaign_id=CAMPAIGN_A, campaign_name="Campaign A")
    history_a.append(
        _metric(
            START + timedelta(days=20),
            campaign_id=CAMPAIGN_A,
            campaign_name="Campaign A",
            clicks=15,
        )
    )
    history_b = _steady_history(20, campaign_id=CAMPAIGN_B, campaign_name="Campaign B")
    history_b.append(
        _metric(
            START + timedelta(days=20),
            campaign_id=CAMPAIGN_B,
            campaign_name="Campaign B",
            clicks=15,
        )
    )
    # Feed B before A — output order must not depend on input order.
    features = engineer_features(history_b + history_a)

    recs = generate_recommendations(features)

    assert [r.campaign_id for r in recs] == [CAMPAIGN_A, CAMPAIGN_B]


def test_rules_tuple_is_in_documented_order() -> None:
    assert [rule.__name__ for rule in RULES] == [
        "evaluate_ctr_drop",
        "evaluate_cpa_spike",
        "evaluate_spend_waste",
        "evaluate_conversion_drop",
    ]


# ---------------------------------------------------------------------------------------------
# Insufficient history: never invent a baseline, never crash.
# ---------------------------------------------------------------------------------------------


def test_cpa_spike_does_not_fire_with_insufficient_baseline_history() -> None:
    history = _steady_history(2)
    history.append(_metric(START + timedelta(days=2), spend="1000"))  # would look like a huge spike
    features = engineer_features(history)

    recs = generate_recommendations(features)

    assert "cpa_spike" not in [r.rule_id for r in recs]


def test_conversion_drop_does_not_fire_or_crash_when_previous_day_is_missing() -> None:
    # A caller passing only the latest record (no history at all) still carries a real, AI-01
    # computed conversion_trend baked into that FeatureRecord from whenever it was engineered.
    # This must be treated as untrustworthy context here, not indexed into blindly.
    history = _steady_history(20)
    history.append(_metric(START + timedelta(days=20), spend="60", conversions=6, revenue="180"))
    features = engineer_features(history)
    latest_only = (features[-1],)  # deliberately drop everything but the last record

    recs = generate_recommendations(latest_only)

    assert recs == ()


# ---------------------------------------------------------------------------------------------
# Anomaly / forecast enrichment — optional in every sense.
# ---------------------------------------------------------------------------------------------


def _ctr_drop_features() -> tuple[FeatureRecord, ...]:
    history = _steady_history(20)
    history.append(_metric(START + timedelta(days=20), clicks=15))
    return tuple(engineer_features(history))


def _conversion_drop_features() -> tuple[FeatureRecord, ...]:
    history = _steady_history(20)
    history.append(_metric(START + timedelta(days=20), spend="60", conversions=6, revenue="180"))
    return tuple(engineer_features(history))


def _forecast(
    *,
    campaign_id: UUID = CAMPAIGN_A,
    organization_id: UUID = ORG,
    metric_name: str = "conversions",
    forecast_date: date,
    value: Decimal | None,
    model_used: ModelUsed = ModelUsed.LINEAR_REGRESSION,
    horizon_days: int = 7,
) -> ForecastRecord:
    """Build a real AI-03 ``ForecastRecord`` fixture (only ``spend``/``conversions``/``roas``
    are ever real metric names here — AI-03's ``SUPPORTED_METRICS``)."""

    return ForecastRecord(
        organization_id=organization_id,
        campaign_id=campaign_id,
        metric_name=metric_name,
        forecast_date=forecast_date,
        horizon_days=horizon_days,
        value=value,
        ci_lower=(value - Decimal("1")) if value is not None else None,
        ci_upper=(value + Decimal("1")) if value is not None else None,
        model_used=model_used,
        generated_from_date=START + timedelta(days=20),
    )


def test_matching_anomaly_sets_source_id_and_increases_confidence_and_severity() -> None:
    features = _ctr_drop_features()
    baseline_recs = generate_recommendations(features)
    anomaly_id = UUID("30000000-0000-0000-0000-000000000001")
    anomaly = AnomalySignal(
        organization_id=ORG,
        campaign_id=CAMPAIGN_A,
        metric_name="ctr",
        direction="below",
        severity="high",
        anomaly_score=Decimal("3.4"),
        id=anomaly_id,
    )

    recs = generate_recommendations(features, anomalies=[anomaly])

    assert len(recs) == 1
    assert recs[0].source_anomaly_id == anomaly_id
    assert recs[0].confidence_score > baseline_recs[0].confidence_score
    assert recs[0].severity > baseline_recs[0].severity
    assert any("Confirmed by anomaly detection" in line for line in recs[0].evidence)


def test_anomaly_in_opposite_direction_is_not_matched() -> None:
    features = _ctr_drop_features()
    baseline_recs = generate_recommendations(features)
    anomaly = AnomalySignal(
        organization_id=ORG,
        campaign_id=CAMPAIGN_A,
        metric_name="ctr",
        direction="above",  # our rule fired on a "below" drop — directions disagree
        severity="high",
        anomaly_score=Decimal("3.4"),
    )

    recs = generate_recommendations(features, anomalies=[anomaly])

    assert recs[0].source_anomaly_id is None
    assert recs[0].confidence_score == baseline_recs[0].confidence_score


def test_anomaly_for_a_campaign_outside_this_run_is_ignored_not_an_error() -> None:
    features = _ctr_drop_features()
    unrelated_campaign = UUID("20000000-0000-0000-0000-000000000099")
    anomaly = AnomalySignal(
        organization_id=ORG,
        campaign_id=unrelated_campaign,
        metric_name="ctr",
        direction="below",
        severity="high",
        anomaly_score=Decimal("3.4"),
    )

    recs = generate_recommendations(features, anomalies=[anomaly])

    assert len(recs) == 1
    assert recs[0].source_anomaly_id is None


def test_anomaly_with_mismatched_organization_raises() -> None:
    features = _ctr_drop_features()
    anomaly = AnomalySignal(
        organization_id=OTHER_ORG,
        campaign_id=CAMPAIGN_A,
        metric_name="ctr",
        direction="below",
        severity="high",
        anomaly_score=Decimal("3.4"),
    )

    with pytest.raises(RecommendationDataError, match="organization_id"):
        generate_recommendations(features, anomalies=[anomaly])


def test_forecast_with_mismatched_organization_raises() -> None:
    features = _conversion_drop_features()
    forecast = _forecast(
        organization_id=OTHER_ORG, forecast_date=START + timedelta(days=27), value=Decimal("4")
    )

    with pytest.raises(RecommendationDataError, match="organization_id"):
        generate_recommendations(features, forecasts=[forecast])


def test_matching_forecast_is_appended_to_evidence() -> None:
    features = _conversion_drop_features()
    forecast = _forecast(
        metric_name="conversions",
        forecast_date=date(2026, 2, 1),
        value=Decimal("4"),
        model_used=ModelUsed.LINEAR_REGRESSION,
        horizon_days=7,
    )

    recs = generate_recommendations(features, forecasts=[forecast])

    assert len(recs) == 1
    evidence = " ".join(recs[0].evidence)
    assert "Forecast projects conversions" in evidence
    assert "2026-02-01" in evidence
    assert "7 days" in evidence
    assert "linear_regression" in evidence


def test_nearest_forecast_date_is_used_when_multiple_exist() -> None:
    features = _conversion_drop_features()
    far = _forecast(metric_name="conversions", forecast_date=date(2026, 3, 1), value=Decimal("3"))
    near = _forecast(metric_name="conversions", forecast_date=date(2026, 2, 1), value=Decimal("4"))

    recs = generate_recommendations(features, forecasts=[far, near])

    assert any("2026-02-01" in line for line in recs[0].evidence)
    assert not any("2026-03-01" in line for line in recs[0].evidence)


def test_insufficient_history_forecast_is_never_matched() -> None:
    # AI-03's real degraded representation: model_used=INSUFFICIENT_HISTORY with value=None.
    # This must never surface in evidence, and must never crash the (Decimal | None) formatting.
    features = _conversion_drop_features()
    degraded = _forecast(
        metric_name="conversions",
        forecast_date=date(2026, 2, 1),
        value=None,
        model_used=ModelUsed.INSUFFICIENT_HISTORY,
    )

    recs = generate_recommendations(features, forecasts=[degraded])

    assert len(recs) == 1
    assert not any("Forecast projects" in line for line in recs[0].evidence)


# ---------------------------------------------------------------------------------------------
# Scoring: exact, bounded, deterministic.
# ---------------------------------------------------------------------------------------------


def _trigger(*, severe: bool = False, matched_anomaly: AnomalySignal | None = None) -> RuleTrigger:
    return RuleTrigger(
        rule_id="ctr_drop",
        organization_id=ORG,
        campaign_id=CAMPAIGN_A,
        campaign_name="Campaign A",
        metric_name="ctr",
        direction="below",
        observed_value=Decimal("0.01"),
        reference_value=Decimal("0.05"),
        relative_change=Decimal("0.8"),
        severe=severe,
        matched_anomaly=matched_anomaly,
    )


def test_score_trigger_base_case_is_exact() -> None:
    confidence, severity = score_trigger(_trigger())
    assert confidence == CONFIDENCE_BASE
    assert severity == SEVERITY_BASE


def test_score_trigger_severe_case_is_exact() -> None:
    confidence, severity = score_trigger(_trigger(severe=True))
    assert confidence == CONFIDENCE_BASE + CONFIDENCE_MAGNITUDE_BONUS_CAP
    assert severity == SEVERITY_BASE + 1


def test_score_trigger_high_severity_anomaly_case_is_exact() -> None:
    anomaly = AnomalySignal(
        organization_id=ORG,
        campaign_id=CAMPAIGN_A,
        metric_name="ctr",
        direction="below",
        severity="high",
        anomaly_score=Decimal("4"),
    )
    confidence, severity = score_trigger(_trigger(matched_anomaly=anomaly))
    assert confidence == CONFIDENCE_BASE + CONFIDENCE_ANOMALY_BONUS
    assert severity == SEVERITY_BASE + SEVERITY_HIGH_ANOMALY_BONUS


def test_score_trigger_never_exceeds_contract_range() -> None:
    anomaly = AnomalySignal(
        organization_id=ORG,
        campaign_id=CAMPAIGN_A,
        metric_name="ctr",
        direction="below",
        severity="high",
        anomaly_score=Decimal("9"),
    )
    confidence, severity = score_trigger(_trigger(severe=True, matched_anomaly=anomaly))
    assert Decimal("0") <= confidence <= Decimal("1")
    assert 1 <= severity <= 5


# ---------------------------------------------------------------------------------------------
# Explainability formatter: exact known text.
# ---------------------------------------------------------------------------------------------


def test_build_evidence_ctr_drop_exact_text() -> None:
    trigger = RuleTrigger(
        rule_id="ctr_drop",
        organization_id=ORG,
        campaign_id=CAMPAIGN_A,
        campaign_name="Summer Sale",
        metric_name="ctr",
        direction="below",
        observed_value=Decimal("0.015"),
        reference_value=Decimal("0.045"),
        relative_change=Decimal("0.6667"),
        severe=True,
    )

    problem, action, evidence = build_evidence(trigger)

    assert problem == "Click-through rate has dropped for Summer Sale"
    assert action == "Refresh the ad creative and review audience targeting for Summer Sale."
    assert evidence == ("CTR is 1.5%, down from a 7-day average of 4.5% (66.7% drop).",)


def test_recommendation_is_a_plain_dataclass_matching_the_recommendations_table_shape() -> None:
    # Sanity check that the public type has exactly the fields a persistence layer (AI-06) would
    # need to map onto the real `recommendations` columns, plus the documented extra `rule_id`.
    fields = {f for f in Recommendation.__dataclass_fields__}
    assert fields == {
        "organization_id",
        "campaign_id",
        "source_anomaly_id",
        "problem",
        "evidence",
        "suggested_action",
        "confidence_score",
        "risk_rating",
        "severity",
        "rule_id",
    }


# ---------------------------------------------------------------------------------------------
# Downstream correlation (AI-05): (campaign_id, rule_id) must be a safe, unique join key.
# ---------------------------------------------------------------------------------------------


def test_recommendation_campaign_and_rule_id_pairs_are_unique() -> None:
    # AI-05's action_simulations rows have a NOT NULL FK back to a recommendation, but no DB `id`
    # exists yet at this stage (AI-06 mints it). Two campaigns, each firing two different rules,
    # confirms (campaign_id, rule_id) is a safe join key for that correlation: no collisions, and
    # a two-recommendation campaign is unambiguous.
    history_a = _steady_history(20, campaign_id=CAMPAIGN_A, campaign_name="Campaign A")
    history_a.append(
        _metric(
            START + timedelta(days=20),
            campaign_id=CAMPAIGN_A,
            campaign_name="Campaign A",
            conversions=5,
        )
    )
    history_b = _steady_history(20, campaign_id=CAMPAIGN_B, campaign_name="Campaign B")
    history_b.append(
        _metric(
            START + timedelta(days=20),
            campaign_id=CAMPAIGN_B,
            campaign_name="Campaign B",
            clicks=15,
        )
    )
    features = engineer_features(history_a + history_b)

    recs = generate_recommendations(features)

    assert len(recs) == 3  # campaign A fires two rules (cpa_spike + conversion_drop), B fires one
    keys = [(r.campaign_id, r.rule_id) for r in recs]
    assert len(keys) == len(set(keys))
