"""Export deterministic synthetic AI-03 forecast and backtest evidence."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pandas as pd
from sawakli.ai.features import FeatureRecord
from sawakli.ai.forecasting import (
    ForecastRecord,
    evaluate_forecasters,
    generate_forecasts,
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
FOREST_CAMPAIGN_ID = UUID("20000000-0000-0000-0000-000000000001")
REGRESSION_CAMPAIGN_ID = UUID("20000000-0000-0000-0000-000000000002")
AVERAGE_CAMPAIGN_ID = UUID("20000000-0000-0000-0000-000000000003")
OUTPUT_DIRECTORY = Path("artifacts/ai03")


def _json_default(value: object) -> str:
    return str(value)


def _feature(
    campaign_id: UUID, campaign_name: str, day: date, spend: Decimal, conversions: int
) -> FeatureRecord:
    """Construct one complete, representative AI-01-shaped feature record."""

    revenue = spend * Decimal("2.4")
    return FeatureRecord(
        organization_id=ORGANIZATION_ID,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        platform="meta",
        date=day,
        spend=spend,
        impressions=10_000,
        clicks=300,
        conversions=conversions,
        revenue=revenue,
        sessions=None,
        bounces=None,
        session_duration=None,
        ctr=Decimal("0.03"),
        cpc=spend / Decimal(300),
        cpa=spend / Decimal(conversions),
        roas=Decimal("2.4"),
        bounce_rate=None,
        rolling_ctr_7d=None,
        rolling_ctr_14d=None,
        rolling_cpc_7d=None,
        rolling_cpc_14d=None,
        spend_trend=None,
        conversion_trend=None,
        roas_trend=None,
    )


def synthetic_features() -> list[FeatureRecord]:
    """Return fixed histories that exercise forest, regression, and mean fallbacks."""

    start = date(2026, 1, 1)
    specifications = (
        (FOREST_CAMPAIGN_ID, "Synthetic Forest", 35),
        (REGRESSION_CAMPAIGN_ID, "Synthetic Regression", 14),
        (AVERAGE_CAMPAIGN_ID, "Synthetic Average", 7),
    )
    return [
        _feature(
            campaign_id,
            campaign_name,
            start + timedelta(days=index),
            Decimal(100) + Decimal(index * 2) + Decimal(index % 3),
            8 + (index % 4),
        )
        for campaign_id, campaign_name, count in specifications
        for index in range(count)
    ]


def _svg_plot(features: list[FeatureRecord], forecast: ForecastRecord) -> str:
    """Render one simple forecast point and confidence band as dependency-free SVG."""

    history = sorted(
        (
            record
            for record in features
            if record.campaign_id == forecast.campaign_id
            and forecast.metric_name == "spend"
        ),
        key=lambda record: record.date,
    )
    values = [record.spend for record in history]
    assert (
        forecast.value is not None
        and forecast.ci_lower is not None
        and forecast.ci_upper is not None
    )
    lower = min(*values, forecast.ci_lower)
    upper = max(*values, forecast.ci_upper)
    span = upper - lower or Decimal(1)
    width, height, padding = 720, 360, 45

    def x(index: int) -> float:
        return padding + index * (width - 2 * padding) / len(values)

    def y(value: Decimal) -> float:
        return float(
            height - padding - (value - lower) * Decimal(height - 2 * padding) / span
        )

    points = " ".join(
        f"{x(index):.1f},{y(value):.1f}" for index, value in enumerate(values)
    )
    forecast_x = x(len(values))
    band_top, band_bottom = y(forecast.ci_upper), y(forecast.ci_lower)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{padding}" y="24" font-family="sans-serif" font-size="16">Synthetic Forest — spend forecast ({forecast.horizon_days} days)</text>
  <line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#334155"/>
  <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#334155"/>
  <polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="2"/>
  <rect x="{forecast_x - 8:.1f}" y="{band_top:.1f}" width="16" height="{band_bottom - band_top:.1f}" fill="#93c5fd" opacity="0.65"/>
  <line x1="{forecast_x:.1f}" y1="{band_top:.1f}" x2="{forecast_x:.1f}" y2="{band_bottom:.1f}" stroke="#1d4ed8" stroke-width="2"/>
  <circle cx="{forecast_x:.1f}" cy="{y(forecast.value):.1f}" r="5" fill="#dc2626"/>
  <text x="{forecast_x - 24:.1f}" y="{height - 16}" font-family="sans-serif" font-size="12">forecast</text>
</svg>'''


def main() -> None:
    """Generate and persist synthetic forecasts, metrics, and one SVG plot."""

    features = synthetic_features()
    forecasts = generate_forecasts(features)
    evaluations = evaluate_forecasters(features)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    forecast_rows = [asdict(record) for record in forecasts]
    evaluation_rows = [asdict(record) for record in evaluations]
    pd.DataFrame(forecast_rows).to_csv(OUTPUT_DIRECTORY / "forecasts.csv", index=False)
    pd.DataFrame(evaluation_rows).to_csv(
        OUTPUT_DIRECTORY / "evaluations.csv", index=False
    )
    (OUTPUT_DIRECTORY / "forecasts.json").write_text(
        json.dumps(forecast_rows, default=_json_default, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIRECTORY / "evaluations.json").write_text(
        json.dumps(evaluation_rows, default=_json_default, indent=2), encoding="utf-8"
    )
    plotted_forecast = next(
        record
        for record in forecasts
        if record.campaign_id == FOREST_CAMPAIGN_ID
        and record.metric_name == "spend"
        and record.horizon_days == 7
    )
    (OUTPUT_DIRECTORY / "forecast.svg").write_text(
        _svg_plot(features, plotted_forecast), encoding="utf-8"
    )
    print(pd.DataFrame(forecast_rows).to_string(index=False))
    print(pd.DataFrame(evaluation_rows).to_string(index=False))
    print(f"Wrote synthetic evidence to {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()
