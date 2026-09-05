from uuid import UUID

from sqlalchemy.orm import Session

from sawakli.ai.features import DatabaseDataLoader, engineer_features
from sawakli.ai.forecasting import evaluate_forecasters, generate_forecasts

NOUR_ORG_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def test_seeded_nour_data_generates_read_only_forecasts_and_evaluations(
    db_session: Session,
) -> None:
    """Use AI-01's scoped loader only; this test never persists AI-03 output."""

    metrics = DatabaseDataLoader(db_session).load_metrics(NOUR_ORG_ID)
    features = list(engineer_features(metrics))

    forecasts = generate_forecasts(features)
    evaluations = evaluate_forecasters(features)

    assert forecasts
    assert evaluations
    assert all(record.organization_id == NOUR_ORG_ID for record in forecasts)
    assert all(record.organization_id == NOUR_ORG_ID for record in evaluations)
