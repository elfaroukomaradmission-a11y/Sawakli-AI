"""Public in-memory entry points for deterministic AI-03 forecasting."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sawakli.ai.features import FeatureRecord

from .forecasters import FORECASTERS, Forecaster, Observation
from .schemas import ForecastDataError, ForecastEvaluation, ForecastRecord, ModelUsed

SUPPORTED_METRICS = ("spend", "conversions", "roas")
DEFAULT_HORIZONS = (7, 14, 30)


def generate_forecasts(
    features: list[FeatureRecord], horizons: tuple[int, ...] = DEFAULT_HORIZONS
) -> list[ForecastRecord]:
    """Project supported metrics using the first eligible fallback model.

    Input is already an AI-01 output. This function validates only the local
    forecasting boundary and performs no database read or write.
    """

    normalized_horizons = _validate_horizons(horizons)
    groups = _group_features(features)
    forecasts: list[ForecastRecord] = []
    for (campaign_id, metric_name), records in groups:
        history = _history_for_metric(records, metric_name)
        generated_from_date = history[-1].date if history else records[-1].date
        for horizon_days in normalized_horizons:
            model = _select_forecaster(history)
            if model is None:
                forecasts.append(
                    ForecastRecord(
                        organization_id=records[0].organization_id,
                        campaign_id=campaign_id,
                        metric_name=metric_name,
                        forecast_date=generated_from_date + timedelta(days=horizon_days),
                        horizon_days=horizon_days,
                        value=None,
                        ci_lower=None,
                        ci_upper=None,
                        model_used=ModelUsed.INSUFFICIENT_HISTORY,
                        generated_from_date=generated_from_date,
                    )
                )
                continue
            value, ci_lower, ci_upper = model.forecast(history, horizon_days)
            forecasts.append(
                ForecastRecord(
                    organization_id=records[0].organization_id,
                    campaign_id=campaign_id,
                    metric_name=metric_name,
                    forecast_date=generated_from_date + timedelta(days=horizon_days),
                    horizon_days=horizon_days,
                    value=value,
                    ci_lower=ci_lower,
                    ci_upper=ci_upper,
                    model_used=_model_used(model),
                    generated_from_date=generated_from_date,
                )
            )
    return forecasts


def evaluate_forecasters(
    features: list[FeatureRecord], holdout_points: int = 7
) -> list[ForecastEvaluation]:
    """Return comparable deterministic backtest errors for every supported model."""

    # Delayed import keeps evaluation dependent on the engine's input grouping
    # helpers without making package import order circular.
    from .evaluation import evaluate_forecasters as _evaluate_forecasters

    return _evaluate_forecasters(features, holdout_points)


def _group_features(
    features: Iterable[FeatureRecord],
) -> list[tuple[tuple[UUID, str], tuple[FeatureRecord, ...]]]:
    source = tuple(features)
    if not source:
        return []
    if any(not isinstance(record, FeatureRecord) for record in source):
        raise ForecastDataError("forecast input must contain FeatureRecord values")
    organizations = {record.organization_id for record in source}
    if len(organizations) != 1:
        raise ForecastDataError("forecast input must contain exactly one organization")

    grouped: dict[tuple[UUID, str], list[FeatureRecord]] = defaultdict(list)
    seen: set[tuple[UUID, object]] = set()
    for record in source:
        if not record.organization_id or not record.campaign_id:
            raise ForecastDataError("FeatureRecord requires organization_id and campaign_id")
        key = (record.campaign_id, record.date)
        if key in seen:
            raise ForecastDataError("duplicate campaign/date FeatureRecord")
        seen.add(key)
        for metric_name in SUPPORTED_METRICS:
            grouped[(record.campaign_id, metric_name)].append(record)

    result: list[tuple[tuple[UUID, str], tuple[FeatureRecord, ...]]] = []
    for key in sorted(grouped, key=lambda item: (item[0].int, item[1])):
        records = tuple(sorted(grouped[key], key=lambda record: record.date))
        campaign_organizations = {record.organization_id for record in records}
        if len(campaign_organizations) != 1:
            raise ForecastDataError("one campaign_id cannot belong to multiple organizations")
        result.append((key, records))
    return result


def _history_for_metric(
    records: Sequence[FeatureRecord], metric_name: str
) -> tuple[Observation, ...]:
    observations: list[Observation] = []
    for record in records:
        raw_value: Decimal | int | None
        if metric_name == "spend":
            raw_value = record.spend
        elif metric_name == "conversions":
            raw_value = record.conversions
        elif metric_name == "roas":
            raw_value = record.roas
        else:
            raise ForecastDataError(f"unsupported forecast metric: {metric_name}")
        if raw_value is None:
            continue
        value = raw_value if isinstance(raw_value, Decimal) else Decimal(raw_value)
        if not value.is_finite():
            raise ForecastDataError(f"{metric_name} must be finite")
        observations.append(Observation(date=record.date, value=value))
    return tuple(observations)


def _validate_horizons(horizons: Iterable[int]) -> tuple[int, ...]:
    result = tuple(sorted(set(horizons)))
    if not result:
        raise ForecastDataError("at least one forecast horizon is required")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in result
    ):
        raise ForecastDataError("forecast horizons must be positive integers")
    return result


def _select_forecaster(history: Sequence[Observation]) -> Forecaster | None:
    return next(
        (
            forecaster
            for forecaster in FORECASTERS
            if len(history) >= forecaster.minimum_required_history
        ),
        None,
    )


def _model_used(forecaster: Forecaster) -> ModelUsed:
    return ModelUsed(forecaster.name)
