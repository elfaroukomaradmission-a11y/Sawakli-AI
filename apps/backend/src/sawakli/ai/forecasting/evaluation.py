"""Comparable deterministic rolling-origin backtesting for AI-03."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from decimal import Decimal, localcontext

from sawakli.ai.features import FeatureRecord
from sawakli.ai.features.metrics import FEATURE_DECIMAL_CONTEXT, decimal_sum

from .engine import DEFAULT_HORIZONS, SUPPORTED_METRICS, _group_features, _history_for_metric
from .forecasters import FORECASTERS, GAP_HANDLING_RULE, Forecaster, Observation
from .schemas import ForecastEvaluation, ModelUsed

DEFAULT_HOLDOUT_POINTS = 7
# Evaluation deliberately uses the single shared forecaster gap policy.
BACKTEST_GAP_HANDLING_RULE = GAP_HANDLING_RULE


def evaluate_forecasters(
    features: list[FeatureRecord], holdout_points: int = DEFAULT_HOLDOUT_POINTS
) -> list[ForecastEvaluation]:
    """Backtest every model on the same viable last-K observed targets.

    A target is eligible only when its date is exactly ``horizon_days`` after an
    observed origin. Each model is refit from observations through that origin.
    Origins must satisfy the largest model minimum, ensuring all three models
    receive identical target dates and therefore comparable errors. The shared
    :data:`GAP_HANDLING_RULE` governs history selection; no date is fabricated.
    """

    if (
        isinstance(holdout_points, bool)
        or not isinstance(holdout_points, int)
        or holdout_points <= 0
    ):
        raise ValueError("holdout_points must be a positive integer")
    groups = _group_features(features)
    evaluations: list[ForecastEvaluation] = []
    for (campaign_id, metric_name), records in groups:
        if metric_name not in SUPPORTED_METRICS:
            continue
        history = _history_for_metric(records, metric_name)
        for horizon_days in DEFAULT_HORIZONS:
            for forecaster in sorted(FORECASTERS, key=lambda item: item.name):
                predictions, actuals = _backtest(
                    history, forecaster, horizon_days, holdout_points
                )
                mae, rmse, mape = _errors(predictions, actuals)
                evaluations.append(
                    ForecastEvaluation(
                        organization_id=records[0].organization_id,
                        campaign_id=campaign_id,
                        metric_name=metric_name,
                        model_used=ModelUsed(forecaster.name),
                        horizon_days=horizon_days,
                        mae=mae,
                        rmse=rmse,
                        mape=mape,
                    )
                )
    return sorted(
        evaluations,
        key=lambda item: (
            item.campaign_id.int,
            item.metric_name,
            item.model_used.value,
            item.horizon_days,
        ),
    )


def _backtest(
    history: tuple[Observation, ...],
    forecaster: Forecaster,
    horizon_days: int,
    holdout_points: int,
) -> tuple[tuple[Decimal, ...], tuple[Decimal, ...]]:
    # Use the RF threshold for every model so results compare like-for-like.
    shared_minimum = max(item.minimum_required_history for item in FORECASTERS)
    targets = history[-holdout_points:]
    predictions: list[Decimal] = []
    actuals: list[Decimal] = []
    for target in targets:
        origin_date = target.date - timedelta(days=horizon_days)
        origin_index = next(
            (index for index, item in enumerate(history) if item.date == origin_date), None
        )
        if origin_index is None:
            continue
        training = history[: origin_index + 1]
        if len(training) < shared_minimum:
            continue
        value, _, _ = forecaster.forecast(training, horizon_days)
        predictions.append(value)
        actuals.append(target.value)
    return tuple(predictions), tuple(actuals)


def _errors(
    predictions: Sequence[Decimal], actuals: Sequence[Decimal]
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if not predictions:
        return None, None, None
    with localcontext(FEATURE_DECIMAL_CONTEXT):
        errors = tuple(
            abs(prediction - actual)
            for prediction, actual in zip(predictions, actuals, strict=True)
        )
        mae = decimal_sum(errors) / Decimal(len(errors))
        rmse = (decimal_sum(error**2 for error in errors) / Decimal(len(errors))).sqrt()
        percentage_errors = tuple(
            abs(prediction - actual) / abs(actual)
            for prediction, actual in zip(predictions, actuals, strict=True)
            if actual != 0
        )
        mape = (
            decimal_sum(percentage_errors) / Decimal(len(percentage_errors))
            if percentage_errors
            else None
        )
    return mae, rmse, mape
