from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StagedCreativeRow:
    external_id: str | None
    creative_type: str | None
    headline: str | None
    asset_url: str | None


@dataclass(frozen=True)
class StagedAdRow:
    external_id: str | None
    name: str
    status_raw: str | None
    creative: StagedCreativeRow | None = None


@dataclass(frozen=True)
class StagedAdGroupRow:
    external_id: str | None
    name: str
    status_raw: str | None
    ad: StagedAdRow | None = None


@dataclass(frozen=True)
class StagedCampaignRow:
    organization_id: UUID
    data_source_id: UUID
    provider: str
    external_id: str | None
    campaign_name: str
    platform_raw: str | None
    status_raw: str | None
    objective: str | None
    budget: float | None
    start_date_raw: str | None
    end_date_raw: str | None
    ad_group: StagedAdGroupRow | None = None
