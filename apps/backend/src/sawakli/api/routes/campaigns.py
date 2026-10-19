import datetime as dt
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from sawakli.api.deps import DbSession, OrgAuth, apply_org_scope
from sawakli.api.schemas.campaigns import CampaignPublic
from sawakli.api.schemas.metrics import DailyMetricPublic
from sawakli.db.models.campaign import Campaign
from sawakli.db.models.daily_metric import DailyMetric

router = APIRouter(prefix="/api/orgs/{org}/campaigns", tags=["Dashboard"])


@router.get("", response_model=list[CampaignPublic])
def list_campaigns(auth: OrgAuth, db: DbSession) -> list[Campaign]:
    stmt = apply_org_scope(select(Campaign).order_by(Campaign.name), Campaign, auth.organization.id)
    campaigns = db.scalars(stmt).all()
    return list(campaigns)


@router.get("/{campaign_id}", response_model=CampaignPublic)
def get_campaign(campaign_id: UUID, auth: OrgAuth, db: DbSession) -> Campaign:
    stmt = apply_org_scope(
        select(Campaign).where(Campaign.id == campaign_id),
        Campaign,
        auth.organization.id,
    )
    campaign = db.scalar(stmt)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return campaign


@router.get("/{campaign_id}/metrics", response_model=list[DailyMetricPublic])
def get_campaign_metrics(
    campaign_id: UUID,
    auth: OrgAuth,
    db: DbSession,
    date_from: Annotated[dt.date, Query(alias="from")],
    date_to: Annotated[dt.date, Query(alias="to")],
) -> list[DailyMetricPublic]:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="'from' must not be after 'to'")

    # The campaign must belong to the token's org, otherwise 404 (not an empty list).
    campaign_stmt = apply_org_scope(
        select(Campaign.id).where(Campaign.id == campaign_id),
        Campaign,
        auth.organization.id,
    )
    if db.scalar(campaign_stmt) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    stmt = apply_org_scope(
        select(DailyMetric)
        .where(DailyMetric.campaign_id == campaign_id)
        .where(DailyMetric.date >= date_from)
        .where(DailyMetric.date <= date_to)
        .order_by(DailyMetric.date),
        DailyMetric,
        auth.organization.id,
    )
    return [DailyMetricPublic.from_row(row) for row in db.scalars(stmt)]
