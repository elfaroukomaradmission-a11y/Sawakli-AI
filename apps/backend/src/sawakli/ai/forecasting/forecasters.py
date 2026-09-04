"""Deterministic AI-03 forecasters.

GAP_HANDLING_RULE: gaps are never interpolated or fabricated.  Every forecaster
uses its last N *observed* points, skipping dates without a usable value; its
minimum history is an observed-point count, not a calendar span.  Linear
regression (and the forest's matching input) nevertheless use actual calendar
offsets from the first selected observation.  This preserves elapsed-time
slopes across gaps without starving models that need more observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from typing import Protocol

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from sawakli.ai.features.metrics import FEATURE_DECIMAL_CONTEXT, decimal_sum

GAP_HANDLING_RULE = (
    "Gaps are never interpolated or fabricated; use the last N observed points, "
    "but calculate time features from actual calendar-day offsets."
)
Z_MULTIPLIER = Decimal("1.96")
MOVING_AVERAGE_WINDOW = 7
LINEAR_REGRESSION_WINDOW = 14
RANDOM_FOREST_WINDOW = 21
RANDOM_FOREST_RANDOM_STATE = 42
RANDOM_FOREST_ESTIMATORS = 100
RANDOM_FOREST_CI_PERCENTILES = (2.5, 97.5)


@dataclass(frozen=True, slots=True)
class Observation:
    """A usable observed value for one campaign metric."""

    date: date
    value: Decimal


class Forecaster(Protocol):
    """Contract shared by deterministic AI-03 forecasting models."""

    name: str
    minimum_required_history: int

    def forecast(
        self, history: tuple[Observation, ...], horizon_days: int
    ) -> tuple[Decimal, Decimal, Decimal]: ...


def _last_observed(history: tuple[Observation, ...], count: int) -> tuple[Observation, ...]:
    if len(history) < count:
        raise ValueError("history does not meet the declared minimum")
    return history[-count:]


def _standard_deviation(values: tuple[Decimal, ...], centre: Decimal) -> Decimal:
    """Population standard deviation with the pinned AI Decimal context."""

    if not values:
        return Decimal(0)
    with localcontext(FEATURE_DECIMAL_CONTEXT):
        variance = decimal_sum((value - centre) ** 2 for value in values) / Decimal(len(values))
        return variance.sqrt()


def _bounded_interval(value: Decimal, lower: Decimal, upper: Decimal) -> tuple[Decimal, Decimal]:
    return min(lower, value), max(upper, value)


class MovingAverageForecaster:
    """Seven-observed-point mean with a 1.96-sigma residual interval."""

    name = "moving_average"
    minimum_required_history = MOVING_AVERAGE_WINDOW

    def forecast(
        self, history: tuple[Observation, ...], horizon_days: int
    ) -> tuple[Decimal, Decimal, Decimal]:
        window = _last_observed(history, MOVING_AVERAGE_WINDOW)
        values = tuple(item.value for item in window)
        with localcontext(FEATURE_DECIMAL_CONTEXT):
            value = decimal_sum(values) / Decimal(len(values))
            residual_stddev = _standard_deviation(values, value)
            spread = Z_MULTIPLIER * residual_stddev
            lower, upper = _bounded_interval(value, value - spread, value + spread)
        return value, lower, upper


class LinearRegressionForecaster:
    """Fourteen-observed-point closed-form OLS using real calendar offsets."""

    name = "linear_regression"
    minimum_required_history = LINEAR_REGRESSION_WINDOW

    def forecast(
        self, history: tuple[Observation, ...], horizon_days: int
    ) -> tuple[Decimal, Decimal, Decimal]:
        window = _last_observed(history, LINEAR_REGRESSION_WINDOW)
        offsets = tuple(Decimal((item.date - window[0].date).days) for item in window)
        values = tuple(item.value for item in window)
        with localcontext(FEATURE_DECIMAL_CONTEXT):
            x_mean = decimal_sum(offsets) / Decimal(len(offsets))
            y_mean = decimal_sum(values) / Decimal(len(values))
            denominator = decimal_sum((offset - x_mean) ** 2 for offset in offsets)
            slope = (
                Decimal(0)
                if denominator == 0
                else decimal_sum(
                    (offset - x_mean) * (value - y_mean)
                    for offset, value in zip(offsets, values, strict=True)
                )
                / denominator
            )
            intercept = y_mean - slope * x_mean
            target_offset = Decimal((window[-1].date - window[0].date).days + horizon_days)
            value = intercept + slope * target_offset
            residuals = tuple(
                observed - (intercept + slope * offset)
                for offset, observed in zip(offsets, values, strict=True)
            )
            residual_stddev = _standard_deviation(residuals, Decimal(0))
            spread = Z_MULTIPLIER * residual_stddev
            lower, upper = _bounded_interval(value, value - spread, value + spread)
        return value, lower, upper


class RandomForestForecaster:
    """Fixed-seed forest using only calendar offset -> value input.

    Decimal values cross to float solely inside this class because sklearn and
    numpy require it.  Results cross back through ``Decimal(str(float))`` before
    leaving the forecaster; the rest of AI-03 remains Decimal-based.
    """

    name = "random_forest"
    minimum_required_history = RANDOM_FOREST_WINDOW

    def forecast(
        self, history: tuple[Observation, ...], horizon_days: int
    ) -> tuple[Decimal, Decimal, Decimal]:
        window = _last_observed(history, RANDOM_FOREST_WINDOW)
        first_date = window[0].date
        x = np.array([[(item.date - first_date).days] for item in window], dtype=float)
        y = np.array([float(item.value) for item in window], dtype=float)
        model = RandomForestRegressor(
            n_estimators=RANDOM_FOREST_ESTIMATORS,
            random_state=RANDOM_FOREST_RANDOM_STATE,
            n_jobs=1,
        )
        model.fit(x, y)
        target = np.array([[(window[-1].date - first_date).days + horizon_days]], dtype=float)
        prediction = float(model.predict(target)[0])
        tree_predictions = np.array(
            [float(tree.predict(target)[0]) for tree in model.estimators_], dtype=float
        )
        lower_float, upper_float = np.percentile(tree_predictions, RANDOM_FOREST_CI_PERCENTILES)
        value = Decimal(str(prediction))
        lower, upper = _bounded_interval(
            value, Decimal(str(float(lower_float))), Decimal(str(float(upper_float)))
        )
        return value, lower, upper


FORECASTERS: tuple[Forecaster, ...] = (
    RandomForestForecaster(),
    LinearRegressionForecaster(),
    MovingAverageForecaster(),
)
