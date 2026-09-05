"""Export read-only AI-03 forecast and backtest evidence for the Nour demo data.

Run from the repository root after installing the backend package and configuring
DATABASE_URL: ``python scripts/ai03_evidence.py``. Output is intentionally
gitignored because it is generated local evidence, not a shipped artifact.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

import pandas as pd
from sawakli.ai.features import DatabaseDataLoader, engineer_features
from sawakli.ai.forecasting import evaluate_forecasters, generate_forecasts
from sawakli.db.session import SessionLocal

NOUR_ORGANIZATION_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
OUTPUT_DIRECTORY = Path("artifacts/ai03")


def _json_default(value: object) -> str:
    return str(value)


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        metrics = DatabaseDataLoader(session).load_metrics(NOUR_ORGANIZATION_ID)
    features = list(engineer_features(metrics))
    forecasts = generate_forecasts(features)
    evaluations = evaluate_forecasters(features)

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
    print(f"Wrote forecast and evaluation evidence to {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()
