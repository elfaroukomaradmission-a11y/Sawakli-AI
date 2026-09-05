"""Typed, in-memory contracts for AI-03 forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class ForecastDataError(Exception):
    """Raised when FeatureRecord input cannot safely enter forecasting."""


class ModelUsed(StrEnum):
    """The model selected by the deterministic fallback hierarchy."""

    MOVING_AVERAGE = "moving_average"
    LINEAR_REGRESSION = "linear_regression"
    RANDOM_FOREST = "random_forest"
    INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass(frozen=True, slots=True)
class ForecastRecord:
    """One in-memory projection for a supported campaign metric and horizon."""

    organization_id: UUID
    campaign_id: UUID
    metric_name: str
    forecast_date: date
    horizon_days: int
    value: Decimal | None
    ci_lower: Decimal | None
    ci_upper: Decimal | None
    model_used: ModelUsed
    generated_from_date: date


@dataclass(frozen=True, slots=True)
class ForecastEvaluation:
    """Deterministic backtest errors for one campaign, metric, model, and horizon."""

    organization_id: UUID
    campaign_id: UUID
    metric_name: str
    model_used: ModelUsed
    horizon_days: int
    mae: Decimal | None
    rmse: Decimal | None
    mape: Decimal | None
