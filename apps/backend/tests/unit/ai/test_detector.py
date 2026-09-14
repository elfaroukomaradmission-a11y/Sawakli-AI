from datetime import date
from decimal import Decimal
from uuid import uuid4

from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.features import FeatureRecord


def make_record(
    *,
    campaign_id,
    day: int,
    spend: str = "100",
    ctr: str = "0.05",
    cpc: str = "2",
    cpa: str = "20",
    roas: str = "3",
    spend_trend: str | None = None,
    conversion_trend: str | None = None,
    roas_trend: str | None = None,
) -> FeatureRecord:
    return FeatureRecord(
        organization_id=uuid4(),
        campaign_id=campaign_id,
        campaign_name="Nour Campaign",
        platform="meta",
        date=date(2026, 1, day),
        spend=Decimal(spend),
        impressions=1000,
        clicks=50,
        conversions=5,
        revenue=Decimal("300"),
        sessions=None,
        bounces=None,
        session_duration=None,
        ctr=Decimal(ctr),
        cpc=Decimal(cpc),
        cpa=Decimal(cpa),
        roas=Decimal(roas),
        bounce_rate=None,
        rolling_ctr_7d=None,
        rolling_ctr_14d=None,
        rolling_cpc_7d=None,
        rolling_cpc_14d=None,
        spend_trend=Decimal(spend_trend) if spend_trend else None,
        conversion_trend=(
            Decimal(conversion_trend) if conversion_trend else None
        ),
        roas_trend=Decimal(roas_trend) if roas_trend else None,
    )


def test_empty_input_returns_empty_result():
    assert detect_anomalies([]) == ()


def test_insufficient_history_is_not_an_anomaly():
    campaign_id = uuid4()

    records = [
        make_record(campaign_id=campaign_id, day=i)
        for i in range(1, 5)
    ]

    results = detect_anomalies(records)

    assert len(results) == 4
    assert all(result.severity == "normal" for result in results)


def test_normal_campaign_has_low_anomaly_score():
    campaign_id = uuid4()

    records = [
        make_record(campaign_id=campaign_id, day=i)
        for i in range(1, 11)
    ]

    results = detect_anomalies(records)

    assert len(results) == 10
    assert all(result.score < Decimal("0.8") for result in results)


def test_detector_is_deterministic():
    campaign_id = uuid4()

    records = [
        make_record(campaign_id=campaign_id, day=i)
        for i in range(1, 11)
    ]

    first = detect_anomalies(records)
    second = detect_anomalies(records)

    assert first == second


def test_campaigns_are_evaluated_independently():
    campaign_a = uuid4()
    campaign_b = uuid4()

    records = [
        *[
            make_record(campaign_id=campaign_a, day=i)
            for i in range(1, 11)
        ],
        *[
            make_record(campaign_id=campaign_b, day=i)
            for i in range(1, 11)
        ],
    ]

    results = detect_anomalies(records)

    assert len(results) == 20
    assert {
        result.campaign_id for result in results
    } == {campaign_a, campaign_b}

def test_detector_finds_strong_downward_anomaly():
    campaign_id = uuid4()

    records = [
        make_record(
            campaign_id=campaign_id,
            day=i,
            roas="3.0",
            cpc="2.0",
            conversion_trend="0.0",
            roas_trend="0.0",
        )
        for i in range(1, 11)
    ]

    # Day 11 = deliberately abnormal
    records.append(
        make_record(
            campaign_id=campaign_id,
            day=11,
            roas="0.5",
            cpc="8.0",
            conversion_trend="-0.80",
            roas_trend="-0.83",
        )
    )

    results = detect_anomalies(records)

    abnormal = results[-1]

    assert abnormal.score > Decimal("0.40")
    assert abnormal.severity in {"medium", "high", "critical"}
    assert abnormal.direction == "down"
    assert abnormal.reasons
    
def test_detector_finds_strong_upward_anomaly():
    campaign_id = uuid4()

    records = [
        make_record(
            campaign_id=campaign_id,
            day=i,
            roas="3.0",
            cpc="2.0",
            conversion_trend="0.0",
            roas_trend="0.0",
        )
        for i in range(1, 11)
    ]

    records.append(
        make_record(
            campaign_id=campaign_id,
            day=11,
            roas="10.0",
            cpc="0.5",
            conversion_trend="2.0",
            roas_trend="2.3",
        )
    )

    results = detect_anomalies(records)

    abnormal = results[-1]

    assert abnormal.score > Decimal("0.40")
    assert abnormal.severity in {"medium", "high", "critical"}
    assert abnormal.direction == "up"
    assert abnormal.reasons