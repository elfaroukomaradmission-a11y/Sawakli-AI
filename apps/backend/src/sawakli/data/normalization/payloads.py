from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class CampaignUpsertPayload:
    organization_id: UUID
    data_source_id: UUID
    external_id: str | None
    name: str
    platform: str | None
    objective: str | None
    status: str | None
    budget: float | None
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class AdGroupUpsertPayload:
    organization_id: UUID
    campaign_id: UUID
    external_id: str | None
    name: str
    status: str | None


@dataclass(frozen=True)
class AdUpsertPayload:
    organization_id: UUID
    ad_group_id: UUID
    external_id: str | None
    name: str
    status: str | None


@dataclass(frozen=True)
class CreativeUpsertPayload:
    organization_id: UUID
    ad_id: UUID
    external_id: str | None
    creative_type: str | None
    headline: str | None
    asset_url: str | None
