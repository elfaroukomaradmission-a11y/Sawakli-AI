from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from sawakli.data.staging.models import StagedCampaignRow

from .normalize import (
    normalize_ad,
    normalize_ad_group,
    normalize_campaign,
    normalize_creative,
)
from .upsert import (
    upsert_ad,
    upsert_ad_group,
    upsert_campaign,
    upsert_creative,
)


@dataclass(frozen=True)
class NormalizationResult:
    campaign_id: UUID
    ad_group_id: UUID | None
    ad_id: UUID | None
    creative_id: UUID | None


@dataclass(frozen=True)
class BatchResult:
    results: list[NormalizationResult]


def normalize_and_upsert(
    db: Session,
    row: StagedCampaignRow,
) -> NormalizationResult:
    campaign = normalize_campaign(row)
    campaign_id = upsert_campaign(db, campaign)

    ad_group_id: UUID | None = None
    ad_id: UUID | None = None
    creative_id: UUID | None = None

    if row.ad_group is not None:
        ad_group = normalize_ad_group(
            row.ad_group,
            campaign_id,
            row.organization_id,
        )
        ad_group_id = upsert_ad_group(db, ad_group)

        if row.ad_group.ad is not None:
            ad = normalize_ad(
                row.ad_group.ad,
                ad_group_id,
                row.organization_id,
            )
            ad_id = upsert_ad(db, ad)

            if row.ad_group.ad.creative is not None:
                creative = normalize_creative(
                    row.ad_group.ad.creative,
                    ad_id,
                    row.organization_id,
                )
                creative_id = upsert_creative(db, creative)

    return NormalizationResult(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        ad_id=ad_id,
        creative_id=creative_id,
    )


def normalize_and_upsert_batch(
    db: Session,
    rows: list[StagedCampaignRow],
) -> BatchResult:
    results = [normalize_and_upsert(db, row) for row in rows]
    return BatchResult(results=results)
