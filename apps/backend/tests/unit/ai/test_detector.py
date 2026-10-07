from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import numpy as np
import pytest

from sawakli.ai.anomaly.detector import (
    _build_feature_matrix,
    _iqr_score,
    _robust_z_score,
    detect_anomalies,
)
from sawakli.ai.features import FeatureRecord

TEST_ORGANIZATION_ID = UUID(int=1)


def make_record(
    *,
    campaign_id: UUID,
    day: int,
    organization_id: UUID = TEST_ORGANIZATION_ID,
    spend: str = "100",
    ctr: str = "0.05",
    cpc: str = "2",
    cpa: str = "20",
    roas: str = "3",
    spend_trend: str | None = None,
    conversion_trend: str | None = None,
    roas_trend: str | None = None,
) -> FeatureRecord:
    return FeatureRecord(
        organization_id=organization_id,
        campaign_id=campaign_id,
        campaign_name="Nour Campaign",
        platform="meta",
        date=date(2026, 1, day),
        spend=Decimal(spend),
        impressions=1000,
        clicks=50,
        conversions=5,
        revenue=Decimal("300"),
        sessions=None,
        bounces=None,
        session_duration=None,
        ctr=Decimal(ctr),
        cpc=Decimal(cpc),
        cpa=Decimal(cpa),
        roas=Decimal(roas),
        bounce_rate=None,
        rolling_ctr_7d=None,
        rolling_ctr_14d=None,
        rolling_cpc_7d=None,
        rolling_cpc_14d=None,
        spend_trend=Decimal(spend_trend) if spend_trend else None,
        conversion_trend=(Decimal(conversion_trend) if conversion_trend else None),
        roas_trend=Decimal(roas_trend) if roas_trend else None,
    )


def test_empty_input_returns_empty_result():
    assert detect_anomalies([]) == ()


def test_insufficient_history_is_not_an_anomaly():
    campaign_id = uuid4()

    records = [make_record(campaign_id=campaign_id, day=i) for i in range(1, 5)]

    results = detect_anomalies(records)

    assert len(results) == 4
    assert all(result.severity == "normal" for result in results)


def test_normal_campaign_has_low_anomaly_score():
    campaign_id = uuid4()

    records = [make_record(campaign_id=campaign_id, day=i) for i in range(1, 11)]

    results = detect_anomalies(records)

    assert len(results) == 10
    assert all(result.score == Decimal("0") for result in results)
    assert all(result.severity == "normal" for result in results)


def test_detector_is_deterministic():
    campaign_id = uuid4()

    records = [make_record(campaign_id=campaign_id, day=i) for i in range(1, 11)]

    first = detect_anomalies(records)
    second = detect_anomalies(records)

    assert first == second


def test_campaigns_are_evaluated_independently():
    campaign_a = uuid4()
    campaign_b = uuid4()

    records = [
        *[make_record(campaign_id=campaign_a, day=i) for i in range(1, 11)],
        *[make_record(campaign_id=campaign_b, day=i) for i in range(1, 11)],
    ]

    results = detect_anomalies(records)

    assert len(results) == 20
    assert {result.campaign_id for result in results} == {campaign_a, campaign_b}


def test_detector_finds_strong_downward_anomaly():
    campaign_id = uuid4()

    records = [
        make_record(
            campaign_id=campaign_id,
            day=i,
            roas="3.0",
            cpc="2.0",
            conversion_trend="0.0",
            roas_trend="0.0",
        )
        for i in range(1, 11)
    ]

    # Day 11 = deliberately abnormal
    records.append(
        make_record(
            campaign_id=campaign_id,
            day=11,
            roas="0.5",
            cpc="8.0",
            conversion_trend="-0.80",
            roas_trend="-0.83",
        )
    )

    results = detect_anomalies(records)

    abnormal = results[-1]

    assert abnormal.score > Decimal("0.40")
    assert abnormal.severity in {"medium", "high", "critical"}
    assert abnormal.direction == "down"
    assert abnormal.reasons


def test_same_campaign_id_in_two_organizations_has_independent_results():
    campaign_id = uuid4()
    organization_a = UUID(int=10)
    organization_b = UUID(int=20)
    records_a = [
        make_record(campaign_id=campaign_id, organization_id=organization_a, day=i)
        for i in range(1, 11)
    ]
    records_b = [
        make_record(
            campaign_id=campaign_id,
            organization_id=organization_b,
            day=i,
            spend="5000",
            cpc="100",
            cpa="1000",
            roas="0.1",
        )
        for i in range(1, 11)
    ]
    records_b.append(
        make_record(
            campaign_id=campaign_id,
            organization_id=organization_b,
            day=11,
            spend="10000",
            cpc="200",
            cpa="2000",
            roas="0.01",
        )
    )

    combined = detect_anomalies([*records_b, *records_a])

    assert combined == (*detect_anomalies(records_a), *detect_anomalies(records_b))
    assert all(result.score == 0 for result in combined[:10])
    assert combined[-1].score >= Decimal("0.4")


def test_reordering_observations_does_not_change_scores():
    campaign_id = uuid4()
    records = [make_record(campaign_id=campaign_id, day=i) for i in range(1, 11)]
    records.append(make_record(campaign_id=campaign_id, day=11, cpc="8", roas="0.5"))

    expected = detect_anomalies(records)
    shuffled = [records[i] for i in [10, 4, 1, 8, 0, 6, 9, 3, 7, 2, 5]]

    assert detect_anomalies(reversed(records)) == expected
    assert detect_anomalies(shuffled) == expected


def test_statistical_detectors_need_five_earlier_observations():
    campaign_id = uuid4()
    records = [make_record(campaign_id=campaign_id, day=i) for i in range(1, 11)]
    records[2] = replace(records[2], cpc=Decimal("8"))

    third_day = detect_anomalies(records)[2]

    assert third_day.robust_z_score == 0
    assert third_day.iqr_score == 0


def test_missing_matrix_values_use_observed_median_and_drop_unavailable_columns():
    campaign_id = uuid4()
    records = [
        make_record(campaign_id=campaign_id, day=1, ctr="0.04"),
        make_record(campaign_id=campaign_id, day=2, ctr="0.06"),
        replace(make_record(campaign_id=campaign_id, day=3), ctr=None),
    ]

    matrix = _build_feature_matrix(records)

    # Only spend/CTR/CPC/CPA/ROAS are observed; trends/rolling values are absent.
    assert matrix.shape == (3, 5)
    assert matrix[2, 1] == 0.05
    assert np.isfinite(matrix).all()


def test_detector_finds_strong_upward_anomaly():
    campaign_id = uuid4()

    records = [
        make_record(
            campaign_id=campaign_id,
            day=i,
            roas="3.0",
            cpc="2.0",
            conversion_trend="0.0",
            roas_trend="0.0",
        )
        for i in range(1, 11)
    ]

    records.append(
        make_record(
            campaign_id=campaign_id,
            day=11,
            roas="10.0",
            cpc="0.5",
            conversion_trend="2.0",
            roas_trend="2.3",
        )
    )

    results = detect_anomalies(records)

    abnormal = results[-1]

    assert abnormal.score > Decimal("0.40")
    assert abnormal.severity in {"medium", "high", "critical"}
    assert abnormal.direction == "up"
    assert abnormal.reasons


def test_statistical_scores_match_hand_calculated_nonconstant_history():
    campaign_id = UUID(int=30)
    history = [make_record(campaign_id=campaign_id, day=day, spend=str(day)) for day in range(1, 6)]
    current = make_record(campaign_id=campaign_id, day=6, spend="8")
    future = make_record(campaign_id=campaign_id, day=7, spend="1000")
    records = [*history, current, future]

    # History [1, 2, 3, 4, 5]: median=3, MAD=1.
    # Robust contribution: (8 - 3) / (1.4826 * 1 * 6) = 0.562076 rounded.
    assert _robust_z_score(records, current) == (
        Decimal("0.562076"),
        "up",
        ["spend is unusually up"],
    )
    # Q1=2, Q3=4, IQR=2, upper fence=7.
    # IQR contribution: (8 - 7) / (2 * 3) = 0.166667 rounded.
    assert _iqr_score(records, current) == (
        Decimal("0.166667"),
        "up",
        ["spend is outside the normal IQR range"],
    )


@pytest.mark.parametrize("available_history", [4, 5])
def test_statistical_history_gate_counts_available_feature_values(available_history):
    campaign_id = UUID(int=40)
    history = [
        replace(
            make_record(campaign_id=campaign_id, day=day),
            ctr=Decimal("0.05") if day <= available_history else None,
        )
        for day in range(1, 7)
    ]
    current = make_record(campaign_id=campaign_id, day=7, ctr="0.5")
    future = make_record(campaign_id=campaign_id, day=8, ctr="0.05")
    records = [*history, current, future]

    z_score, _, z_reasons = _robust_z_score(records, current)
    iqr_score, _, iqr_reasons = _iqr_score(records, current)

    # Six earlier rows are insufficient when only four CTR values exist.
    # Current and future values must not satisfy the five-observation gate.
    if available_history == 4:
        assert z_score == iqr_score == 0
        assert z_reasons == iqr_reasons == []
    else:
        assert z_score == iqr_score == 1
        assert z_reasons == ["ctr is unusually up"]
        assert iqr_reasons == ["ctr is outside the normal IQR range"]
