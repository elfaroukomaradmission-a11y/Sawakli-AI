"""Controlled synthetic evaluation, separate from Nour/DATA-02 acceptance."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.features import MetricRecord, engineer_features

ORGANIZATION_ID = UUID(int=1)


def make_series(campaign_number: int, scenario: str) -> tuple[MetricRecord, ...]:
    """Twenty baseline days, then one explicitly injected event (or a clean day)."""
    records = []
    for day in range(21):
        spend, clicks, conversions, revenue = Decimal("100"), 50, 5, Decimal("300")
        if day == 20:
            if scenario == "spend_waste":
                spend, revenue = Decimal("300"), Decimal("30")
            elif scenario == "ctr_drop":
                clicks, conversions, revenue = 10, 1, Decimal("30")
            elif scenario == "improvement":
                conversions, revenue = 15, Decimal("900")
        records.append(
            MetricRecord(
                organization_id=ORGANIZATION_ID,
                campaign_id=UUID(int=campaign_number),
                campaign_name=f"Synthetic {scenario} {campaign_number}",
                platform="meta",
                date=date(2026, 1, 1) + timedelta(days=day),
                spend=spend,
                impressions=1000,
                clicks=clicks,
                conversions=conversions,
                revenue=revenue,
            )
        )
    return tuple(records)


def test_controlled_synthetic_events_and_thirty_clean_campaigns():
    """Do not interpret this homogeneous fixture as DATA-02 quality evidence."""
    source = []
    positive_keys = set()
    clean_campaigns = set()
    for campaign_number in range(1, 61):
        scenario = (
            "clean"
            if campaign_number <= 30
            else ("spend_waste", "ctr_drop", "improvement")[(campaign_number - 31) % 3]
        )
        series = make_series(campaign_number, scenario)
        source.extend(series)
        if scenario == "clean":
            clean_campaigns.add(series[0].campaign_id)
        else:
            positive_keys.add((series[-1].campaign_id, series[-1].date))

    results = detect_anomalies(engineer_features(source))
    flagged = {
        (result.campaign_id, result.date) for result in results if result.score >= Decimal("0.4")
    }
    true_positive = len(flagged & positive_keys)
    false_positive = sum(campaign_id in clean_campaigns for campaign_id, _ in flagged)
    flagged_clean_campaigns = {
        campaign_id for campaign_id, _ in flagged if campaign_id in clean_campaigns
    }

    recall = true_positive / len(positive_keys)
    day_fpr = false_positive / (len(clean_campaigns) * 21)
    campaign_fpr = len(flagged_clean_campaigns) / len(clean_campaigns)
    print(
        f"CONTROLLED SYNTHETIC ONLY: TP={true_positive}/30; "
        f"recall={recall:.2%}; clean-day FPR={day_fpr:.2%}; "
        f"clean-campaign FPR={campaign_fpr:.2%}"
    )
    assert len(results) == 1260
    assert recall >= 0.80
    assert day_fpr <= 0.05
    assert campaign_fpr <= 0.05
