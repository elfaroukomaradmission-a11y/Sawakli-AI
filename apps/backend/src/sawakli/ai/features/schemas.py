"""Typed input and output contracts for AI feature engineering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


class FeatureDataError(ValueError):
    """Raised when source data cannot safely enter the feature pipeline."""


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """Canonical campaign-day facts returned by every AI-01 loader."""

    organization_id: UUID
    campaign_id: UUID
    campaign_name: str
    platform: str
    date: date
    spend: Decimal
    impressions: int
    clicks: int
    conversions: int
    revenue: Decimal
    sessions: int | None = None
    bounces: int | None = None
    session_duration: Decimal | None = None


@dataclass(frozen=True, slots=True)
class FeatureRecord:
    """One validated campaign-day observation plus deterministic features."""

    organization_id: UUID
    campaign_id: UUID
    campaign_name: str
    platform: str
    date: date
    spend: Decimal
    impressions: int
    clicks: int
    conversions: int
    revenue: Decimal
    sessions: int | None
    bounces: int | None
    session_duration: Decimal | None
    ctr: Decimal | None
    cpc: Decimal | None
    cpa: Decimal | None
    roas: Decimal | None
    bounce_rate: Decimal | None
    rolling_ctr_7d: Decimal | None
    rolling_ctr_14d: Decimal | None
    rolling_cpc_7d: Decimal | None
    rolling_cpc_14d: Decimal | None
    spend_trend: Decimal | None
    conversion_trend: Decimal | None
    roas_trend: Decimal | None
