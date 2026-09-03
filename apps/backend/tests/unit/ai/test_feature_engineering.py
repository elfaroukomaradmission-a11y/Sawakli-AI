from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from sawakli.ai.features import FeatureDataError, MetricRecord, engineer_features, safe_divide

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
CAMPAIGN_A = UUID("20000000-0000-0000-0000-000000000001")
CAMPAIGN_B = UUID("20000000-0000-0000-0000-000000000002")


def metric(
    day: date,
    *,
    campaign_id: UUID = CAMPAIGN_A,
    spend: str = "100",
    impressions: int = 100,
    clicks: int = 10,
    conversions: int = 2,
    revenue: str = "200",
    sessions: int | None = None,
    bounces: int | None = None,
) -> MetricRecord:
    return MetricRecord(
        organization_id=ORG_ID,
        campaign_id=campaign_id,
        campaign_name="Campaign A" if campaign_id == CAMPAIGN_A else "Campaign B",
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


def test_safe_divide_uses_decimal_and_none_for_zero_denominator() -> None:
    assert safe_divide(1, 4) == Decimal("0.25")
    assert safe_divide(Decimal("10.5"), 2) == Decimal("5.25")
    assert safe_divide(1, 0) is None
    assert safe_divide(-1, 0) is None
    with pytest.raises(ValueError, match="finite"):
        safe_divide(Decimal("Infinity"), 1)


def test_base_kpis_have_exact_known_values() -> None:
    record = metric(
        date(2026, 1, 1),
        spend="100",
        impressions=1000,
        clicks=50,
        conversions=5,
        revenue="300",
        sessions=400,
        bounces=100,
    )

    result = engineer_features([record])[0]

    assert result.ctr == Decimal("0.05")
    assert result.cpc == Decimal("2")
    assert result.cpa == Decimal("20")
    assert result.roas == Decimal("3")
    assert result.bounce_rate == Decimal("0.25")


def test_all_undefined_ratios_use_none_and_never_infinity() -> None:
    record = metric(
        date(2026, 1, 1),
        spend="0",
        impressions=0,
        clicks=0,
        conversions=0,
        revenue="10",
        sessions=0,
        bounces=0,
    )

    result = engineer_features([record])[0]

    assert result.ctr is None
    assert result.cpc is None
    assert result.cpa is None
    assert result.roas is None
    assert result.bounce_rate is None


def test_rolling_windows_are_exact_and_require_full_daily_history() -> None:
    start = date(2026, 1, 1)
    records = [metric(start + timedelta(days=index), clicks=index + 1) for index in range(14)]

    result = engineer_features(records)

    assert all(row.rolling_ctr_7d is None for row in result[:6])
    assert result[6].rolling_ctr_7d == Decimal("0.04")
    assert result[13].rolling_ctr_7d == Decimal("0.11")
    assert all(row.rolling_ctr_14d is None for row in result[:13])
    assert result[13].rolling_ctr_14d == Decimal("0.075")
    assert result[5].rolling_cpc_7d is None
    assert result[6].rolling_cpc_7d == Decimal("25")
    assert result[13].rolling_cpc_14d == Decimal("13.33333333333333333333333333")


def test_rolling_ratios_aggregate_raw_facts_instead_of_averaging_daily_ratios() -> None:
    start = date(2026, 1, 1)
    records: list[MetricRecord] = []
    for index in range(14):
        if index in {0, 7}:
            records.append(
                metric(
                    start + timedelta(days=index),
                    spend="100",
                    impressions=100,
                    clicks=10,
                )
            )
        else:
            records.append(
                metric(
                    start + timedelta(days=index),
                    spend="5",
                    impressions=10,
                    clicks=5,
                )
            )

    result = engineer_features(records)

    # Each seven-day block has clicks=40, impressions=160, and spend=130.
    assert result[6].rolling_ctr_7d == Decimal("0.25")
    assert result[6].rolling_cpc_7d == Decimal("3.25")
    assert result[13].rolling_ctr_7d == Decimal("0.25")
    assert result[13].rolling_cpc_7d == Decimal("3.25")
    # The 14-day window doubles every total, preserving the same ratios.
    assert result[13].rolling_ctr_14d == Decimal("0.25")
    assert result[13].rolling_cpc_14d == Decimal("3.25")
    # Daily means would be 3.1/7 CTR and 16/7 CPC, proving this is weighted.
    assert result[6].rolling_ctr_7d != safe_divide(Decimal("3.1"), 7)
    assert result[6].rolling_cpc_7d != safe_divide(16, 7)


def test_gap_in_dates_makes_full_window_and_day_over_day_trend_unavailable() -> None:
    start = date(2026, 1, 1)
    records = [metric(start + timedelta(days=index)) for index in range(6)]
    records.append(metric(start + timedelta(days=7), spend="120"))

    result = engineer_features(records)

    assert result[-1].rolling_ctr_7d is None
    assert result[-1].spend_trend is None


def test_zero_aggregate_denominator_keeps_rolling_value_missing() -> None:
    start = date(2026, 1, 1)
    records = [
        metric(start + timedelta(days=index), impressions=0, clicks=0, spend="10")
        for index in range(7)
    ]

    result = engineer_features(records)

    assert result[-1].rolling_ctr_7d is None
    assert result[-1].rolling_cpc_7d is None


def test_day_over_day_relative_trends_are_exact() -> None:
    result = engineer_features(
        [
            metric(date(2026, 1, 1), spend="100", conversions=10, revenue="200"),
            metric(date(2026, 1, 2), spend="150", conversions=5, revenue="150"),
        ]
    )

    assert result[0].spend_trend is None
    assert result[1].spend_trend == Decimal("0.5")
    assert result[1].conversion_trend == Decimal("-0.5")
    assert result[1].roas_trend == Decimal("-0.5")


def test_zero_previous_value_makes_relative_trend_unavailable() -> None:
    result = engineer_features(
        [
            metric(date(2026, 1, 1), spend="0", conversions=0),
            metric(date(2026, 1, 2), spend="10", conversions=1),
        ]
    )

    assert result[1].spend_trend is None
    assert result[1].conversion_trend is None
    assert result[1].roas_trend is None


def test_rolling_never_leaks_between_campaigns() -> None:
    start = date(2026, 1, 1)
    records = [metric(start + timedelta(days=index)) for index in range(6)]
    records.append(metric(start + timedelta(days=6), campaign_id=CAMPAIGN_B, clicks=100))

    result = engineer_features(reversed(records))

    assert len(result) == 7
    assert all(row.rolling_ctr_7d is None for row in result)


def test_output_is_sorted_and_deterministic() -> None:
    records = [
        metric(date(2026, 1, 2), campaign_id=CAMPAIGN_B),
        metric(date(2026, 1, 2)),
        metric(date(2026, 1, 1)),
    ]

    first = engineer_features(records)
    second = engineer_features(list(reversed(records)))

    assert first == second
    assert [(row.campaign_id, row.date) for row in first] == [
        (CAMPAIGN_A, date(2026, 1, 1)),
        (CAMPAIGN_A, date(2026, 1, 2)),
        (CAMPAIGN_B, date(2026, 1, 2)),
    ]


@pytest.mark.parametrize(
    "records, message",
    [
        (
            [metric(date(2026, 1, 1)), metric(date(2026, 1, 1))],
            "duplicate campaign/date",
        ),
        ([metric(date(2026, 1, 1), spend="-1")], "spend must be non-negative"),
        (
            [metric(date(2026, 1, 1), sessions=2, bounces=3)],
            "bounces cannot exceed sessions",
        ),
    ],
)
def test_invalid_canonical_records_are_rejected(records: list[MetricRecord], message: str) -> None:
    with pytest.raises(FeatureDataError, match=message):
        engineer_features(records)
