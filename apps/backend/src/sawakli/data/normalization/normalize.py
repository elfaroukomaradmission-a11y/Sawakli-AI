from uuid import UUID

from sawakli.data.staging.models import (
    StagedAdGroupRow,
    StagedAdRow,
    StagedCampaignRow,
    StagedCreativeRow,
    StagedDailyMetricRow,
    StagedGAEventRow,
)
from sawakli.data.validation.mappings import (
    map_external_id,
    map_platform,
    map_status,
    parse_iso_date,
)

from .payloads import (
    AdGroupUpsertPayload,
    AdUpsertPayload,
    CampaignUpsertPayload,
    CreativeUpsertPayload,
    DailyMetricUpsertPayload,
    GAEventUpsertPayload,
)


def normalize_campaign(row: StagedCampaignRow) -> CampaignUpsertPayload:
    return CampaignUpsertPayload(
        organization_id=row.organization_id,
        data_source_id=row.data_source_id,
        external_id=map_external_id(row.external_id),
        name=row.campaign_name,
        platform=map_platform(row.provider, row.platform_raw),
        objective=row.objective,
        status=map_status(row.provider, row.status_raw),
        budget=row.budget,
        start_date=parse_iso_date(row.start_date_raw),
        end_date=parse_iso_date(row.end_date_raw),
    )


def normalize_ad_group(
    row: StagedAdGroupRow,
    campaign_id: UUID,
    organization_id: UUID,
) -> AdGroupUpsertPayload:
    return AdGroupUpsertPayload(
        organization_id=organization_id,
        campaign_id=campaign_id,
        external_id=map_external_id(row.external_id),
        name=row.name,
        status=map_status("csv_demo", row.status_raw),
    )


def normalize_ad(
    row: StagedAdRow,
    ad_group_id: UUID,
    organization_id: UUID,
) -> AdUpsertPayload:
    return AdUpsertPayload(
        organization_id=organization_id,
        ad_group_id=ad_group_id,
        external_id=map_external_id(row.external_id),
        name=row.name,
        status=map_status("csv_demo", row.status_raw),
    )


def normalize_creative(
    row: StagedCreativeRow,
    ad_id: UUID,
    organization_id: UUID,
) -> CreativeUpsertPayload:
    return CreativeUpsertPayload(
        organization_id=organization_id,
        ad_id=ad_id,
        external_id=map_external_id(row.external_id),
        creative_type=row.creative_type,
        headline=row.headline,
        asset_url=row.asset_url,
    )


def normalize_daily_metric(
    row: StagedDailyMetricRow,
    campaign_id: UUID,
    organization_id: UUID,
) -> DailyMetricUpsertPayload:
    metric_date = parse_iso_date(row.date)
    if metric_date is None:
        raise ValueError(f"Invalid metric date: {row.date!r}")

    return DailyMetricUpsertPayload(
        organization_id=organization_id,
        campaign_id=campaign_id,
        date=metric_date,
        spend=float(row.spend),
        impressions=int(row.impressions),
        clicks=int(row.clicks),
        conversions=int(row.conversions),
        revenue=float(row.revenue),
    )


def normalize_ga_event(
    row: StagedGAEventRow,
    campaign_id: UUID,
    organization_id: UUID,
) -> GAEventUpsertPayload:
    event_date = parse_iso_date(row.date)
    if event_date is None:
        raise ValueError(f"Invalid GA event date: {row.date!r}")

    sessions = int(row.sessions) if row.sessions is not None else 0
    bounces = int(row.bounces) if row.bounces is not None else 0
    session_duration = float(row.session_duration) if row.session_duration is not None else None

    return GAEventUpsertPayload(
        organization_id=organization_id,
        campaign_id=campaign_id,
        date=event_date,
        sessions=sessions,
        bounces=bounces,
        session_duration=session_duration,
    )
