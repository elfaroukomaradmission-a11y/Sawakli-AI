from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from sawakli.ai.features import FeatureRecord, MetricRecord, engineer_features
from sawakli.ai.forecasting import (
    ForecastDataError,
    ModelUsed,
    evaluate_forecasters,
    generate_forecasts,
)
from sawakli.ai.forecasting.forecasters import (
    LinearRegressionForecaster,
    MovingAverageForecaster,
    Observation,
    RandomForestForecaster,
)

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORG_ID = UUID("10000000-0000-0000-0000-000000000002")
CAMPAIGN_A = UUID("20000000-0000-0000-0000-000000000001")
CAMPAIGN_B = UUID("20000000-0000-0000-0000-000000000002")


def features_for(
    values: list[Decimal],
    *,
    campaign_id: UUID = CAMPAIGN_A,
    dates: list[date] | None = None,
) -> list[FeatureRecord]:
    start = date(2026, 1, 1)
    observation_dates = dates or [start + timedelta(days=index) for index in range(len(values))]
    records = [
        MetricRecord(
            organization_id=ORG_ID,
            campaign_id=campaign_id,
            campaign_name="Campaign A" if campaign_id == CAMPAIGN_A else "Campaign B",
            platform="meta",
            date=day,
            spend=value,
            impressions=100,
            clicks=10,
            conversions=int(value),
            revenue=value * Decimal("2"),
        )
        for day, value in zip(observation_dates, values, strict=True)
    ]
    return list(engineer_features(records))


def observations(values: list[int]) -> tuple[Observation, ...]:
    start = date(2026, 1, 1)
    return tuple(
        Observation(start + timedelta(days=index), Decimal(value))
        for index, value in enumerate(values)
    )


def test_moving_average_has_hand_calculable_value_and_interval() -> None:
    value, lower, upper = MovingAverageForecaster().forecast(observations(list(range(1, 8))), 7)

    assert value == Decimal("4")
    assert lower < value < upper


def test_linear_regression_has_hand_calculable_projection() -> None:
    # y = 2x + 1 for x = 0..13, so the seven-day-ahead point is y(20) = 41.
    series = observations([2 * index + 1 for index in range(14)])
    value, lower, upper = LinearRegressionForecaster().forecast(series, 7)

    assert value == Decimal("41")
    assert lower == value == upper


def test_random_forest_is_deterministic_and_returns_a_bounded_interval() -> None:
    series = observations(list(range(1, 22)))
    forecaster = RandomForestForecaster()

    first = forecaster.forecast(series, 7)
    second = forecaster.forecast(series, 7)

    assert first == second
    assert first[1] <= first[0] <= first[2]
    # A forest is not extrapolation-exact; this only checks a plausible finite result.
    assert Decimal("1") <= first[0] <= Decimal("21")


@pytest.mark.parametrize(
    "point_count, expected_model",
    [
        (21, ModelUsed.RANDOM_FOREST),
        (14, ModelUsed.LINEAR_REGRESSION),
        (7, ModelUsed.MOVING_AVERAGE),
        (6, ModelUsed.INSUFFICIENT_HISTORY),
    ],
)
def test_fallback_hierarchy_at_every_tier(point_count: int, expected_model: ModelUsed) -> None:
    forecasts = generate_forecasts(
        features_for([Decimal(index + 1) for index in range(point_count)])
    )

    assert {forecast.model_used for forecast in forecasts} == {expected_model}
    if expected_model is ModelUsed.INSUFFICIENT_HISTORY:
        assert all(forecast.value is None for forecast in forecasts)
    else:
        assert all(forecast.value is not None for forecast in forecasts)


def test_gap_handling_uses_last_observed_points_not_calendar_days() -> None:
    values = [Decimal(index) for index in range(1, 8)]
    contiguous = features_for(values)
    gapped_dates = [date(2026, 1, 1) + timedelta(days=index * 2) for index in range(7)]
    gapped = features_for(values, dates=gapped_dates)

    contiguous_forecast = generate_forecasts(contiguous, horizons=(7,))[0]
    gapped_forecast = generate_forecasts(gapped, horizons=(7,))[0]

    assert contiguous_forecast.model_used == ModelUsed.MOVING_AVERAGE
    assert gapped_forecast.model_used == ModelUsed.MOVING_AVERAGE
    assert contiguous_forecast.value == gapped_forecast.value == Decimal("4")


def test_ci_invariant_holds_for_every_forecaster() -> None:
    for forecaster, count in (
        (MovingAverageForecaster(), 7),
        (LinearRegressionForecaster(), 14),
        (RandomForestForecaster(), 21),
    ):
        value, lower, upper = forecaster.forecast(observations(list(range(1, count + 1))), 7)
        assert lower <= value <= upper


def test_flat_history_has_a_defined_zero_width_interval() -> None:
    for forecaster, count in (
        (MovingAverageForecaster(), 7),
        (LinearRegressionForecaster(), 14),
        (RandomForestForecaster(), 21),
    ):
        value, lower, upper = forecaster.forecast(observations([5] * count), 7)
        assert lower <= value <= upper
        assert lower == value == upper


def test_backtesting_has_hand_calculable_mae_and_rmse_for_mean_and_ols() -> None:
    # y = x + 1. Seven calendar-day targets have matching observed origins.
    # The seven-point moving average is always ten below the target; OLS is exact.
    result = evaluate_forecasters(features_for([Decimal(index + 1) for index in range(35)]))
    moving_average = next(
        item
        for item in result
        if item.model_used == ModelUsed.MOVING_AVERAGE and item.horizon_days == 7
    )
    regression = next(
        item
        for item in result
        if item.model_used == ModelUsed.LINEAR_REGRESSION and item.horizon_days == 7
    )

    assert moving_average.mae == Decimal("10")
    assert moving_average.rmse == Decimal("10")
    assert regression.mae == Decimal("0")
    assert regression.rmse == Decimal("0")


def test_backtesting_mape_is_missing_when_all_comparable_actuals_are_zero() -> None:
    values = [Decimal(index + 1) for index in range(28)] + [Decimal(0)] * 7
    result = evaluate_forecasters(features_for(values))

    moving_average = next(
        item
        for item in result
        if item.model_used == ModelUsed.MOVING_AVERAGE and item.horizon_days == 7
    )
    assert moving_average.mae is not None
    assert moving_average.rmse is not None
    assert moving_average.mape is None


def test_entrypoints_are_deterministic_when_input_order_changes() -> None:
    records = features_for([Decimal(index + 1) for index in range(35)]) + features_for(
        [Decimal(index + 2) for index in range(35)], campaign_id=CAMPAIGN_B
    )

    first_forecasts = generate_forecasts(records)
    second_forecasts = generate_forecasts(list(reversed(records)))
    first_evaluations = evaluate_forecasters(records)
    second_evaluations = evaluate_forecasters(list(reversed(records)))

    assert first_forecasts == second_forecasts
    assert first_evaluations == second_evaluations


def test_campaign_isolation_and_mixed_organization_rejection() -> None:
    campaign_a = features_for([Decimal(1)] * 7)
    campaign_b = features_for([Decimal(100)] * 7, campaign_id=CAMPAIGN_B)
    forecasts = generate_forecasts(campaign_a + campaign_b, horizons=(7,))

    values_by_campaign = {
        forecast.campaign_id: forecast.value
        for forecast in forecasts
        if forecast.metric_name == "spend"
    }
    assert values_by_campaign == {CAMPAIGN_A: Decimal("1"), CAMPAIGN_B: Decimal("100")}

    foreign = replace(campaign_b[0], organization_id=OTHER_ORG_ID)
    with pytest.raises(ForecastDataError, match="exactly one organization"):
        generate_forecasts(campaign_a + [foreign])
