"""AI-02 interpretable anomaly detection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from sklearn.ensemble import IsolationForest

from sawakli.ai.features import FeatureRecord

# Features produced by AI-01 that AI-02 will inspect.
DEFAULT_FEATURES = (
    "spend",
    "ctr",
    "cpc",
    "cpa",
    "roas",
    "spend_trend",
    "conversion_trend",
    "roas_trend",
    "rolling_ctr_7d",
    "rolling_ctr_14d",
    "rolling_cpc_7d",
    "rolling_cpc_14d",
)


@dataclass(frozen=True, slots=True)
class AnomalyResult:
    """Final AI-02 anomaly result for one campaign-day."""

    organization_id: object
    campaign_id: object
    campaign_name: str
    date: object

    score: Decimal
    severity: str
    direction: str

    robust_z_score: Decimal
    iqr_score: Decimal
    isolation_score: Decimal

    reasons: tuple[str, ...]


def detect_anomalies(
    records: Iterable[FeatureRecord],
    *,
    contamination: float = 0.05,
    random_state: int = 42,
) -> tuple[AnomalyResult, ...]:
    """Detect campaign anomalies using a Z-score/IQR/Isolation Forest ensemble.

    The input must already be AI-01 FeatureRecords.
    """

    records = tuple(records)

    if not records:
        return ()

    # AI-02 evaluates each campaign independently.
    grouped: dict[object, list[FeatureRecord]] = {}

    for record in records:
        grouped.setdefault(record.campaign_id, []).append(record)

    results: list[AnomalyResult] = []

    for campaign_records in grouped.values():
        results.extend(
            _detect_campaign_anomalies(
                campaign_records,
                contamination=contamination,
                random_state=random_state,
            )
        )

    return tuple(
        sorted(
            results,
            key=lambda result: (
                getattr(result.campaign_id, "int", 0),
                result.date,
            ),
        )
    )


def _detect_campaign_anomalies(
    records: list[FeatureRecord],
    *,
    contamination: float,
    random_state: int,
) -> list[AnomalyResult]:
    """Detect anomalies inside one campaign's history."""

    if not records:
        return []

    # We need enough history to establish a useful baseline.
    if len(records) < 5:
        return [_normal_result(record) for record in records]

    feature_values = _build_feature_matrix(records)

    # ---------------------------------------------------------
    # 1. Isolation Forest
    # ---------------------------------------------------------
    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=200,
    )

    model.fit(feature_values)

    isolation_raw = -model.decision_function(feature_values)

    isolation_scores = _normalize_scores(isolation_raw)

    results: list[AnomalyResult] = []

    for index, record in enumerate(records):
        z_score, z_direction, z_reasons = _robust_z_score(
            records,
            record,
        )

        iqr_score, iqr_direction, iqr_reasons = _iqr_score(
            records,
            record,
        )

        isolation_score = Decimal(str(round(float(isolation_scores[index]), 6)))

        # -----------------------------------------------------
        # 2. Ensemble
        # -----------------------------------------------------
        final_score = (
            Decimal("0.40") * z_score
            + Decimal("0.20") * iqr_score
            + Decimal("0.40") * isolation_score
        )

        final_score = min(max(final_score, Decimal("0")), Decimal("1"))

        severity = _severity(final_score)

        direction = _overall_direction(
            record,
            records,
        )

        reasons = tuple(dict.fromkeys([*z_reasons, *iqr_reasons]))

        results.append(
            AnomalyResult(
                organization_id=record.organization_id,
                campaign_id=record.campaign_id,
                campaign_name=record.campaign_name,
                date=record.date,
                score=final_score,
                severity=severity,
                direction=direction,
                robust_z_score=z_score,
                iqr_score=iqr_score,
                isolation_score=isolation_score,
                reasons=reasons,
            )
        )

    return results


def _build_feature_matrix(
    records: list[FeatureRecord],
) -> np.ndarray:
    """Build the Isolation Forest input matrix.

    Missing AI-01 features are replaced with that feature's campaign median
    only for the machine-learning matrix. They are never treated as zero.
    """

    matrix: list[list[float]] = []

    medians: dict[str, float] = {}

    for feature_name in DEFAULT_FEATURES:
        values = [
            float(value)
            for record in records
            if (value := getattr(record, feature_name)) is not None
        ]

        medians[feature_name] = float(np.median(values)) if values else 0.0

    for record in records:
        row: list[float] = []

        for feature_name in DEFAULT_FEATURES:
            value = getattr(record, feature_name)

            if value is None:
                row.append(medians[feature_name])
            else:
                row.append(float(value))

        matrix.append(row)

    return np.asarray(matrix, dtype=float)


def _robust_z_score(
    records: list[FeatureRecord],
    record: FeatureRecord,
) -> tuple[Decimal, str, list[str]]:
    """Compare the current record against previous campaign history."""

    strongest_score = Decimal("0")
    strongest_direction = "normal"
    reasons: list[str] = []

    history = [item for item in records if item.date < record.date]

    if len(history) < 5:
        return Decimal("0"), "normal", []

    for feature_name in DEFAULT_FEATURES:
        current = getattr(record, feature_name)

        if current is None:
            continue

        values = [
            float(value) for item in history if (value := getattr(item, feature_name)) is not None
        ]

        if len(values) < 5:
            continue

        median_value = float(np.median(values))

        absolute_deviations = [abs(value - median_value) for value in values]

        mad = float(np.median(absolute_deviations))
        current_value = float(current)

        # Constant historical value.
        if mad == 0:
            if current_value == median_value:
                continue

            score = Decimal("1")
        else:
            robust_z = abs((current_value - median_value) / (1.4826 * mad))

            score = Decimal(str(round(min(robust_z / 6.0, 1.0), 6)))

        if score > strongest_score:
            strongest_score = score

            strongest_direction = "up" if current_value > median_value else "down"

            reasons = [f"{feature_name} is unusually {strongest_direction}"]

    return strongest_score, strongest_direction, reasons


def _iqr_score(
    records: list[FeatureRecord],
    record: FeatureRecord,
) -> tuple[Decimal, str, list[str]]:
    """Compare the current record against previous campaign history."""

    strongest_score = Decimal("0")
    strongest_direction = "normal"
    reasons: list[str] = []

    history = [item for item in records if item.date < record.date]

    if len(history) < 5:
        return Decimal("0"), "normal", []

    for feature_name in DEFAULT_FEATURES:
        current = getattr(record, feature_name)

        if current is None:
            continue

        values = sorted(
            float(value) for item in history if (value := getattr(item, feature_name)) is not None
        )

        if len(values) < 5:
            continue

        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        current_value = float(current)

        # Constant historical value.
        if iqr == 0:
            if current_value == q1:
                continue

            score = Decimal("1")

            direction = "up" if current_value > q1 else "down"

        else:
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            if current_value < lower:
                distance = (lower - current_value) / iqr
                direction = "down"
            elif current_value > upper:
                distance = (current_value - upper) / iqr
                direction = "up"
            else:
                continue

            score = Decimal(str(round(min(distance / 3.0, 1.0), 6)))

        if score > strongest_score:
            strongest_score = score
            strongest_direction = direction
            reasons = [f"{feature_name} is outside the normal IQR range"]

    return strongest_score, strongest_direction, reasons


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    """Normalize Isolation Forest anomaly scores into [0, 1]."""

    minimum = float(scores.min())
    maximum = float(scores.max())

    if maximum == minimum:
        return np.zeros_like(scores)

    return (scores - minimum) / (maximum - minimum)


def _severity(score: Decimal) -> str:
    """Convert the ensemble score into a human-readable severity."""

    if score >= Decimal("0.80"):
        return "critical"

    if score >= Decimal("0.60"):
        return "high"

    if score >= Decimal("0.40"):
        return "medium"

    if score >= Decimal("0.20"):
        return "low"

    return "normal"


def _combine_direction(
    z_direction: str,
    iqr_direction: str,
) -> str:
    """Combine directional evidence from the interpretable detectors."""

    if z_direction == "normal" and iqr_direction == "normal":
        return "normal"

    if z_direction == iqr_direction:
        return z_direction

    if z_direction == "normal":
        return iqr_direction

    if iqr_direction == "normal":
        return z_direction

    return "mixed"


def _normal_result(record: FeatureRecord) -> AnomalyResult:
    """Return a safe result when there is insufficient campaign history."""

    return AnomalyResult(
        organization_id=record.organization_id,
        campaign_id=record.campaign_id,
        campaign_name=record.campaign_name,
        date=record.date,
        score=Decimal("0"),
        severity="normal",
        direction="normal",
        robust_z_score=Decimal("0"),
        iqr_score=Decimal("0"),
        isolation_score=Decimal("0"),
        reasons=("insufficient campaign history",),
    )


def _overall_direction(
    record: FeatureRecord,
    records: list[FeatureRecord],
) -> str:
    """Determine overall campaign direction from abnormal feature movements."""

    history = [item for item in records if item.date < record.date]

    if len(history) < 5:
        return "normal"

    up_score = 0.0
    down_score = 0.0

    # Higher value = better business performance.
    positive_features = {
        "ctr",
        "conversions",
        "roas",
        "conversion_trend",
        "roas_trend",
    }

    # Higher value = worse business performance.
    negative_features = {
        "cpc",
        "cpa",
        "spend_trend",
    }

    for feature_name in DEFAULT_FEATURES:
        current = getattr(record, feature_name)

        if current is None:
            continue

        values = [
            float(value) for item in history if (value := getattr(item, feature_name)) is not None
        ]

        if len(values) < 5:
            continue

        baseline = float(np.median(values))
        current_value = float(current)

        if current_value == baseline:
            continue

        movement = abs(current_value - baseline)

        if feature_name in positive_features:
            if current_value > baseline:
                up_score += movement
            else:
                down_score += movement

        elif feature_name in negative_features:
            if current_value < baseline:
                up_score += movement
            else:
                down_score += movement

    if up_score == 0 and down_score == 0:
        return "normal"

    if up_score > down_score:
        return "up"

    if down_score > up_score:
        return "down"

    return "mixed"
