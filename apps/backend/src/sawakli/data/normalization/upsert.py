from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from sawakli.db.tables import (
    ad_groups_table,
    ads_table,
    campaigns_table,
    creatives_table,
)

from .payloads import (
    AdGroupUpsertPayload,
    AdUpsertPayload,
    CampaignUpsertPayload,
    CreativeUpsertPayload,
)


def _set_org(db: Session, organization_id: UUID) -> None:
    """Set the RLS organization context on the current transaction."""
    db.execute(
        sa.text("SELECT set_config('app.current_org_id', :org_id, true)"),
        {"org_id": str(organization_id)},
    )


def upsert_campaign(db: Session, payload: CampaignUpsertPayload) -> UUID:
    """Insert or update a campaign."""
    _set_org(db, payload.organization_id)

    values = {
        "organization_id": payload.organization_id,
        "data_source_id": payload.data_source_id,
        "external_id": payload.external_id,
        "name": payload.name,
        "platform": payload.platform,
        "objective": payload.objective,
        "status": payload.status,
        "budget": payload.budget,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
    }

    update = {
        "name": payload.name,
        "platform": payload.platform,
        "objective": payload.objective,
        "status": payload.status,
        "budget": payload.budget,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "updated_at": sa.func.current_timestamp(),
    }

    stmt = insert(campaigns_table).values(**values)

    if payload.external_id:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                campaigns_table.c.data_source_id,
                campaigns_table.c.external_id,
            ],
            index_where=campaigns_table.c.external_id.is_not(None),
            set_=update,
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                campaigns_table.c.data_source_id,
                campaigns_table.c.name,
                campaigns_table.c.platform,
            ],
            index_where=campaigns_table.c.external_id.is_(None),
            set_=update,
        )

    return cast(
        UUID,
        db.execute(stmt.returning(campaigns_table.c.id)).scalar_one(),
    )


def upsert_ad_group(db: Session, payload: AdGroupUpsertPayload) -> UUID:
    """Insert or update an ad group."""
    _set_org(db, payload.organization_id)

    stmt = insert(ad_groups_table).values(
        campaign_id=payload.campaign_id,
        external_id=payload.external_id,
        name=payload.name,
        status=payload.status,
    )

    if payload.external_id:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ad_groups_table.c.campaign_id,
                ad_groups_table.c.external_id,
            ],
            index_where=ad_groups_table.c.external_id.is_not(None),
            set_={
                "name": payload.name,
                "status": payload.status,
            },
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ad_groups_table.c.campaign_id,
                ad_groups_table.c.name,
            ],
            index_where=ad_groups_table.c.external_id.is_(None),
            set_={
                "name": payload.name,
                "status": payload.status,
            },
        )

    return cast(
        UUID,
        db.execute(stmt.returning(ad_groups_table.c.id)).scalar_one(),
    )


def upsert_ad(db: Session, payload: AdUpsertPayload) -> UUID:
    """Insert or update an ad."""
    _set_org(db, payload.organization_id)

    stmt = insert(ads_table).values(
        ad_group_id=payload.ad_group_id,
        external_id=payload.external_id,
        name=payload.name,
        status=payload.status,
    )

    if payload.external_id:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ads_table.c.ad_group_id,
                ads_table.c.external_id,
            ],
            index_where=ads_table.c.external_id.is_not(None),
            set_={
                "name": payload.name,
                "status": payload.status,
            },
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ads_table.c.ad_group_id,
                ads_table.c.name,
            ],
            index_where=ads_table.c.external_id.is_(None),
            set_={
                "name": payload.name,
                "status": payload.status,
            },
        )

    return cast(
        UUID,
        db.execute(stmt.returning(ads_table.c.id)).scalar_one(),
    )


def upsert_creative(db: Session, payload: CreativeUpsertPayload) -> UUID:
    """Insert or update a creative."""
    _set_org(db, payload.organization_id)

    values = {
        "ad_id": payload.ad_id,
        "external_id": payload.external_id,
        "creative_type": payload.creative_type,
        "headline": payload.headline,
        "asset_url": payload.asset_url,
    }

    update = {
        "creative_type": payload.creative_type,
        "headline": payload.headline,
        "asset_url": payload.asset_url,
    }

    stmt = insert(creatives_table).values(**values)

    if payload.external_id:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                creatives_table.c.ad_id,
                creatives_table.c.external_id,
            ],
            index_where=creatives_table.c.external_id.is_not(None),
            set_=update,
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                creatives_table.c.ad_id,
                creatives_table.c.headline,
            ],
            index_where=creatives_table.c.external_id.is_(None),
            set_=update,
        )

    return cast(
        UUID,
        db.execute(stmt.returning(creatives_table.c.id)).scalar_one(),
    )