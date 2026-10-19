"""Unit tests for CampaignPublic. No database, no app."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

from sawakli.api.schemas.campaigns import CampaignPublic
from sawakli.db.models.campaign import Campaign, CampaignStatus, Platform


def _campaign(**overrides: object) -> Campaign:
    values: dict[str, object] = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "data_source_id": uuid4(),
        "external_id": "cmp_1001",
        "name": "Summer Sale",
        "platform": Platform.meta,
        "objective": "conversions",
        "status": CampaignStatus.active,
        "budget": Decimal("5000.00"),
        "start_date": dt.date(2026, 6, 1),
        "end_date": None,
    }
    values.update(overrides)
    return Campaign(**values)


def test_campaign_public_maps_fields() -> None:
    campaign = _campaign()

    result = CampaignPublic.model_validate(campaign)

    assert result.id == campaign.id
    assert result.name == "Summer Sale"
    assert result.platform == Platform.meta
    assert result.status == CampaignStatus.active
    assert result.budget == 5000.0
    assert isinstance(result.budget, float)
    assert result.start_date == dt.date(2026, 6, 1)
    assert result.end_date is None


def test_campaign_public_allows_nullable_fields() -> None:
    campaign = _campaign(status=None, budget=None, objective=None, start_date=None)

    result = CampaignPublic.model_validate(campaign)

    assert result.status is None
    assert result.budget is None
    assert result.objective is None
    assert result.start_date is None


def test_campaign_public_does_not_leak_internal_columns() -> None:
    data = CampaignPublic.model_validate(_campaign()).model_dump()

    assert "organization_id" not in data
    assert "data_source_id" not in data
    assert "external_id" not in data
