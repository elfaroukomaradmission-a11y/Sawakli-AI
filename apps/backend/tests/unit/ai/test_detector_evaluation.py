from datetime import date
from decimal import Decimal
from uuid import uuid4

from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.features import FeatureRecord


def make_record(
    campaign_id,
    day: int,
    *,
    abnormal: bool = False,
) -> FeatureRecord:
    return FeatureRecord(
        organization_id=uuid4(),
        campaign_id=campaign_id,
        campaign_name="Seeded Campaign",
        platform="meta",
        date=date(2026, 1, day),
        spend=Decimal("100") if not abnormal else Decimal("300"),
        impressions=1000,
        clicks=50 if not abnormal else 10,
        conversions=5 if not abnormal else 1,
        revenue=Decimal("300") if not abnormal else Decimal("30"),
        sessions=None,
        bounces=None,
        session_duration=None,
        ctr=Decimal("0.05") if not abnormal else Decimal("0.01"),
        cpc=Decimal("2") if not abnormal else Decimal("30"),
        cpa=Decimal("20") if not abnormal else Decimal("300"),
        roas=Decimal("3") if not abnormal else Decimal("0.10"),
        bounce_rate=None,
        rolling_ctr_7d=None,
        rolling_ctr_14d=None,
        rolling_cpc_7d=None,
        rolling_cpc_14d=None,
        spend_trend=Decimal("0") if not abnormal else Decimal("2"),
        conversion_trend=Decimal("0") if not abnormal else Decimal("-0.80"),
        roas_trend=Decimal("0") if not abnormal else Decimal("-0.97"),
    )


def test_seeded_evaluation_meets_ai02_target():
    campaign_id = uuid4()

    records = [
        *[make_record(campaign_id, day) for day in range(1, 11)],
        # Seeded abnormal case.
        make_record(campaign_id, 11, abnormal=True),
    ]

    results = detect_anomalies(records)

    abnormal_result = results[-1]

    # Seeded anomaly must be detected.
    true_positive = abnormal_result.score >= Decimal("0.40")
    assert true_positive

    # Clean history must remain clean.
    clean_results = results[:-1]
    false_positives = sum(result.score >= Decimal("0.40") for result in clean_results)

    false_positive_rate = false_positives / len(clean_results)

    recall = 1.0 if true_positive else 0.0

    print(f"Recall: {recall:.2%}")
    print(f"False-positive rate: {false_positive_rate:.2%}")

    assert recall >= 0.80
    assert false_positive_rate <= 0.05
