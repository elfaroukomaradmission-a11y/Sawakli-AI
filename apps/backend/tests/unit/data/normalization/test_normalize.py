from datetime import date
from uuid import uuid4

from sawakli.data.normalization.normalize import (
    normalize_ad,
    normalize_ad_group,
    normalize_campaign,
    normalize_creative,
    normalize_daily_metric,
    normalize_ga_event,
)
from sawakli.data.staging.models import (
    StagedAdGroupRow,
    StagedAdRow,
    StagedCampaignRow,
    StagedCreativeRow,
    StagedDailyMetricRow,
    StagedGAEventRow,
)


def test_normalize_campaign() -> None:
    organization_id = uuid4()
    data_source_id = uuid4()

    row = StagedCampaignRow(
        organization_id=organization_id,
        data_source_id=data_source_id,
        provider="csv_demo",
        external_id=None,
        campaign_name="Summer Campaign",
        platform_raw=" META ",
        status_raw=None,
        objective=None,
        budget=None,
        start_date_raw="2026-08-30",
        end_date_raw=None,
    )

    payload = normalize_campaign(row)

    assert payload.organization_id == organization_id
    assert payload.data_source_id == data_source_id
    assert payload.external_id is None
    assert payload.name == "Summer Campaign"
    assert payload.platform == "meta"
    assert payload.status is None
    assert payload.start_date == date(2026, 8, 30)
    assert payload.end_date is None


def test_normalize_ad_group() -> None:
    organization_id = uuid4()
    campaign_id = uuid4()

    row = StagedAdGroupRow(
        external_id="group-123",
        name="Summer Group",
        status_raw=None,
    )

    payload = normalize_ad_group(row, campaign_id, organization_id)

    assert payload.organization_id == organization_id
    assert payload.campaign_id == campaign_id
    assert payload.external_id == "group-123"
    assert payload.name == "Summer Group"
    assert payload.status is None


def test_normalize_ad() -> None:
    organization_id = uuid4()
    ad_group_id = uuid4()

    row = StagedAdRow(
        external_id="ad-123",
        name="Summer Ad",
        status_raw=None,
    )

    payload = normalize_ad(row, ad_group_id, organization_id)

    assert payload.organization_id == organization_id
    assert payload.ad_group_id == ad_group_id
    assert payload.external_id == "ad-123"
    assert payload.name == "Summer Ad"
    assert payload.status is None


def test_normalize_creative() -> None:
    organization_id = uuid4()
    ad_id = uuid4()

    row = StagedCreativeRow(
        external_id="creative-123",
        creative_type="image",
        headline="Summer Sale",
        asset_url="https://example.com/image.jpg",
    )

    payload = normalize_creative(row, ad_id, organization_id)

    assert payload.organization_id == organization_id
    assert payload.ad_id == ad_id
    assert payload.external_id == "creative-123"
    assert payload.creative_type == "image"
    assert payload.headline == "Summer Sale"
    assert payload.asset_url == "https://example.com/image.jpg"


def test_normalize_daily_metric() -> None:
    organization_id = uuid4()
    campaign_id = uuid4()

    row = StagedDailyMetricRow(
        date="2026-08-30",
        spend="103.45",
        impressions="1234",
        clicks="42",
        conversions="7",
        revenue="256.87",
    )

    payload = normalize_daily_metric(row, campaign_id, organization_id)

    assert payload.organization_id == organization_id
    assert payload.campaign_id == campaign_id
    assert payload.date == date(2026, 8, 30)
    assert payload.spend == 103.45
    assert payload.impressions == 1234
    assert payload.clicks == 42
    assert payload.conversions == 7
    assert payload.revenue == 256.87


def test_normalize_ga_event() -> None:
    organization_id = uuid4()
    campaign_id = uuid4()

    row = StagedGAEventRow(
        date="2026-08-30",
        sessions="500",
        bounces="150",
        session_duration=None,
    )

    payload = normalize_ga_event(row, campaign_id, organization_id)

    assert payload.organization_id == organization_id
    assert payload.campaign_id == campaign_id
    assert payload.date == date(2026, 8, 30)
    assert payload.sessions == 500
    assert payload.bounces == 150
    assert payload.session_duration is None
