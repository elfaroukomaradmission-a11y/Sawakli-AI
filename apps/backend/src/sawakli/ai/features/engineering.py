"""Single deterministic feature-engineering path for every AI-01 loader."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from .loaders import _validate_records
from .metrics import Numeric, decimal_sum, relative_change, safe_divide
from .schemas import FeatureDataError, FeatureRecord, MetricRecord

ROLLING_WINDOWS = (7, 14)
SHORT_WINDOW, LONG_WINDOW = ROLLING_WINDOWS


def engineer_features(records: Iterable[MetricRecord]) -> tuple[FeatureRecord, ...]:
    """Validate, sort, group, and produce deterministic campaign-day features."""

    source = tuple(records)
    _validate_records(source)
    ordered = sorted(source, key=lambda record: (record.campaign_id.int, record.date))
    by_campaign: dict[UUID, list[MetricRecord]] = defaultdict(list)
    for record in ordered:
        by_campaign[record.campaign_id].append(record)

    features: list[FeatureRecord] = []
    for campaign_id in sorted(by_campaign, key=lambda value: value.int):
        campaign_records = by_campaign[campaign_id]
        organizations = {record.organization_id for record in campaign_records}
        if len(organizations) != 1:
            raise FeatureDataError("one campaign_id cannot belong to multiple organizations")
        campaign_metadata = {(record.campaign_name, record.platform) for record in campaign_records}
        if len(campaign_metadata) != 1:
            raise FeatureDataError("campaign name and platform must be stable across its history")
        features.extend(_engineer_campaign(campaign_records))
    return tuple(features)


def _engineer_campaign(records: Sequence[MetricRecord]) -> list[FeatureRecord]:
    ctr_values = tuple(safe_divide(record.clicks, record.impressions) for record in records)
    cpc_values = tuple(safe_divide(record.spend, record.clicks) for record in records)
    cpa_values = tuple(safe_divide(record.spend, record.conversions) for record in records)
    roas_values = tuple(safe_divide(record.revenue, record.spend) for record in records)
    bounce_values = tuple(
        safe_divide(record.bounces, record.sessions)
        if record.bounces is not None and record.sessions is not None
        else None
        for record in records
    )

    results: list[FeatureRecord] = []
    for index, record in enumerate(records):
        previous_is_yesterday = index > 0 and records[index - 1].date == record.date - timedelta(
            days=1
        )
        previous = records[index - 1] if previous_is_yesterday else None
        previous_roas = roas_values[index - 1] if previous_is_yesterday else None
        current_roas = roas_values[index]
        results.append(
            FeatureRecord(
                organization_id=record.organization_id,
                campaign_id=record.campaign_id,
                campaign_name=record.campaign_name,
                platform=record.platform,
                date=record.date,
                spend=record.spend,
                impressions=record.impressions,
                clicks=record.clicks,
                conversions=record.conversions,
                revenue=record.revenue,
                sessions=record.sessions,
                bounces=record.bounces,
                session_duration=record.session_duration,
                ctr=ctr_values[index],
                cpc=cpc_values[index],
                cpa=cpa_values[index],
                roas=current_roas,
                bounce_rate=bounce_values[index],
                rolling_ctr_7d=_full_daily_window_ratio(
                    records,
                    index,
                    SHORT_WINDOW,
                    numerator=lambda item: item.clicks,
                    denominator=lambda item: item.impressions,
                ),
                rolling_ctr_14d=_full_daily_window_ratio(
                    records,
                    index,
                    LONG_WINDOW,
                    numerator=lambda item: item.clicks,
                    denominator=lambda item: item.impressions,
                ),
                rolling_cpc_7d=_full_daily_window_ratio(
                    records,
                    index,
                    SHORT_WINDOW,
                    numerator=lambda item: item.spend,
                    denominator=lambda item: item.clicks,
                ),
                rolling_cpc_14d=_full_daily_window_ratio(
                    records,
                    index,
                    LONG_WINDOW,
                    numerator=lambda item: item.spend,
                    denominator=lambda item: item.clicks,
                ),
                spend_trend=(
                    relative_change(record.spend, previous.spend) if previous is not None else None
                ),
                conversion_trend=(
                    relative_change(record.conversions, previous.conversions)
                    if previous is not None
                    else None
                ),
                roas_trend=(
                    relative_change(current_roas, previous_roas)
                    if current_roas is not None and previous_roas is not None
                    else None
                ),
            )
        )
    return results


def _full_daily_window_ratio(
    records: Sequence[MetricRecord],
    index: int,
    window: int,
    *,
    numerator: Callable[[MetricRecord], Numeric],
    denominator: Callable[[MetricRecord], Numeric],
) -> Decimal | None:
    start = index - window + 1
    if start < 0:
        return None
    window_records = records[start : index + 1]
    if window_records[-1].date - window_records[0].date != timedelta(days=window - 1):
        return None
    numerator_total = decimal_sum(numerator(record) for record in window_records)
    denominator_total = decimal_sum(denominator(record) for record in window_records)
    return safe_divide(numerator_total, denominator_total)
