import datetime as dt
from decimal import Decimal
from typing import Self

from pydantic import BaseModel

from sawakli.db.models.daily_metric import DailyMetric


def safe_div(numerator: Decimal | int, denominator: Decimal | int) -> float | None:
    """Return numerator / denominator, or None when the denominator is zero."""
    if denominator == 0:
        return None
    return float(Decimal(numerator) / Decimal(denominator))


class DailyMetricPublic(BaseModel):
    date: dt.date
    spend: float
    revenue: float
    clicks: int
    impressions: int
    conversions: int
    ctr: float | None  # clicks / impressions (a ratio, 0.025 = 2.5%)
    cpc: float | None  # spend / clicks
    cpa: float | None  # spend / conversions
    roas: float | None  # revenue / spend

    @classmethod
    def from_row(cls, row: DailyMetric) -> Self:
        return cls(
            date=row.date,
            spend=float(row.spend),
            revenue=float(row.revenue),
            clicks=row.clicks,
            impressions=row.impressions,
            conversions=row.conversions,
            ctr=safe_div(row.clicks, row.impressions),
            cpc=safe_div(row.spend, row.clicks),
            cpa=safe_div(row.spend, row.conversions),
            roas=safe_div(row.revenue, row.spend),
        )
