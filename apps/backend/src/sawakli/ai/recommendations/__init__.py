"""AI-04: rule-based recommendation engine and explainability formatter.

Public entry point: ``generate_recommendations``. See ``docs/ai/AI-04-recommendation-engine.md``
for scope, contracts, and the documented rule thresholds.

Forecast inputs are AI-03's real, public ``ForecastRecord`` / ``ModelUsed``
(``sawakli.ai.forecasting``) — re-exported here for convenience since callers of this package's
``generate_recommendations`` will need them. Anomaly inputs are still this package's own
``AnomalySignal`` stand-in, since AI-02 does not exist yet.
"""

from __future__ import annotations

from sawakli.ai.forecasting import ForecastRecord, ModelUsed

from .engine import generate_recommendations
from .rules import RULES, RuleTrigger
from .schemas import (
    AnomalyDirection,
    AnomalySeverity,
    AnomalySignal,
    Recommendation,
    RecommendationDataError,
    RiskRating,
)

__all__ = [
    "RULES",
    "AnomalyDirection",
    "AnomalySeverity",
    "AnomalySignal",
    "ForecastRecord",
    "ModelUsed",
    "Recommendation",
    "RecommendationDataError",
    "RiskRating",
    "RuleTrigger",
    "generate_recommendations",
]
