"""Unit tests for safe_div and DailyMetricPublic. No database, no app."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest

from sawakli.api.schemas.metrics import DailyMetricPublic, safe_div
from sawakli.db.models.daily_metric import DailyMetric


def _row(
    spend: str = "100.00",
    revenue: str = "400.00",
    clicks: int = 50,
    impressions: int = 1000,
    conversions: int = 5,
) -> DailyMetric:
    return DailyMetric(
        campaign_id=uuid4(),
        organization_id=uuid4(),
        date=dt.date(2026, 1, 1),
        spend=Decimal(spend),
        revenue=Decimal(revenue),
        clicks=clicks,
        impressions=impressions,
        conversions=conversions,
    )


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (10, 4, 2.5),
        (Decimal("7.5"), Decimal("2.5"), 3.0),
        (0, 5, 0.0),
        (Decimal("100.00"), 50, 2.0),
    ],
)
def test_safe_div_normal(
    numerator: Decimal | int, denominator: Decimal | int, expected: float
) -> None:
    assert safe_div(numerator, denominator) == pytest.approx(expected)


@pytest.mark.parametrize("zero", [0, Decimal("0"), Decimal("0.00")])
def test_safe_div_zero_denominator_returns_none(zero: Decimal | int) -> None:
    assert safe_div(10, zero) is None
    assert safe_div(0, zero) is None


def test_from_row_computes_all_ratios() -> None:
    result = DailyMetricPublic.from_row(_row())

    assert result.date == dt.date(2026, 1, 1)
    assert result.spend == pytest.approx(100.0)
    assert result.revenue == pytest.approx(400.0)
    assert result.ctr == pytest.approx(0.05)  # 50 / 1000
    assert result.cpc == pytest.approx(2.0)  # 100 / 50
    assert result.cpa == pytest.approx(20.0)  # 100 / 5
    assert result.roas == pytest.approx(4.0)  # 400 / 100


def test_from_row_returns_plain_numbers_not_decimal() -> None:
    result = DailyMetricPublic.from_row(_row())

    assert isinstance(result.spend, float)
    assert isinstance(result.revenue, float)
    assert isinstance(result.clicks, int)


def test_from_row_all_zero_day_gives_null_ratios() -> None:
    result = DailyMetricPublic.from_row(
        _row(spend="0.00", revenue="0.00", clicks=0, impressions=0, conversions=0)
    )

    assert result.ctr is None
    assert result.cpc is None
    assert result.cpa is None
    assert result.roas is None


def test_from_row_no_conversions_only_cpa_is_null() -> None:
    result = DailyMetricPublic.from_row(_row(revenue="0.00", conversions=0))

    assert result.cpa is None
    assert result.roas == pytest.approx(0.0)  # spend > 0, so ROAS is 0, not null
    assert result.ctr == pytest.approx(0.05)
    assert result.cpc == pytest.approx(2.0)


def test_from_row_zero_spend_gives_null_roas() -> None:
    result = DailyMetricPublic.from_row(_row(spend="0.00", revenue="50.00"))

    assert result.roas is None


def test_public_schema_exposes_only_expected_fields() -> None:
    data = DailyMetricPublic.from_row(_row()).model_dump()

    assert set(data) == {
        "date",
        "spend",
        "revenue",
        "clicks",
        "impressions",
        "conversions",
        "ctr",
        "cpc",
        "cpa",
        "roas",
    }
