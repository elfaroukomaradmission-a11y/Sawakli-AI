"""Ground-truth integrity, honest denominators and the 90-day reference replay."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from sawakli.ai.anomaly.detector import _normal_result, detect_anomalies
from sawakli.ai.features import engineer_features
from tests.fixtures.ai02_benchmark import (
    Benchmark,
    dataset_digest,
    evaluate_results,
    generate_benchmark,
    record_key,
)


def test_benchmark_is_reproducible_and_labels_partition_every_date():
    benchmark = generate_benchmark()
    assert benchmark == generate_benchmark()
    assert len(benchmark.records) == 5400
    assert len(benchmark.events) == 30
    assert len(benchmark.clean_campaigns) == 30
    assert len({r.organization_id for r in benchmark.records}) == 3
    expected = {record_key(record) for record in benchmark.records}
    positive = {
        record_key(record)
        for record in benchmark.records
        if any(
            record.organization_id == event.organization_id
            and record.campaign_id == event.campaign_id
            and event.start <= record.date <= event.end
            for event in benchmark.events
        )
    }
    assert not positive & benchmark.clean_keys
    assert positive | benchmark.clean_keys == expected
    assert {e.scenario for e in benchmark.events} == {"spend_waste", "ctr_drop", "improvement"}
    assert {r.platform for r in benchmark.records} == {"meta", "google"}
    for org, campaign in benchmark.clean_campaigns:
        rows = [
            r for r in benchmark.records if (r.organization_id, r.campaign_id) == (org, campaign)
        ]
        assert len(rows) == 90
        assert max(r.spend for r in rows) > min(r.spend for r in rows) * Decimal("1.10")
        assert all(record_key(r) in benchmark.clean_keys for r in rows)
    assert len(dataset_digest(benchmark)) == 64
    assert (
        dataset_digest(benchmark)
        == "4533a170f07e361b9e9fc77528aa56822fb07fae58a00e1aa1cd7828ee00ad62"
    )
    assert dataset_digest(benchmark) != dataset_digest(
        replace(benchmark, records=benchmark.records[:-1])
    )


def test_evaluation_rejects_missing_and_duplicate_results():
    benchmark = generate_benchmark()
    results = tuple(_normal_result(r) for r in engineer_features(benchmark.records))
    with pytest.raises(ValueError, match="exactly one result"):
        evaluate_results(benchmark, results[:-1])
    with pytest.raises(ValueError, match="exactly one result"):
        evaluate_results(benchmark, (*results, results[0]))
    assert evaluate_results(benchmark, results)["status"] == "FAIL"


def test_evaluation_counts_event_days_and_clean_campaigns_separately():
    source = generate_benchmark()
    event = source.events[0]
    event_rows = [r for r in source.records if r.campaign_id == event.campaign_id]
    positive_rows = [r for r in event_rows if event.start <= r.date <= event.end][:2]
    clean_row = source.records[0]
    records = (*positive_rows, clean_row)
    benchmark = Benchmark(
        records=records,
        events=(replace(event, end=positive_rows[-1].date),),
        clean_keys=frozenset({record_key(clean_row)}),
        clean_campaigns=frozenset({(clean_row.organization_id, clean_row.campaign_id)}),
    )
    results = tuple(
        replace(
            _normal_result(r),
            score=Decimal("0.80")
            if r.date == event.start or r.campaign_id == clean_row.campaign_id
            else Decimal("0.79"),
        )
        for r in engineer_features(records)
    )
    report = evaluate_results(benchmark, results)
    assert report["detected_events"] == 1
    assert report["event_recall"] == "1"
    assert report["day_recall"] == "0.5"
    assert report["false_positive_campaigns"] == 1
    assert report["clean_campaign_fpr"] == "1"
    assert report["clean_day_fpr"] == "1"
    assert report["status"] == "FAIL"


@pytest.mark.parametrize("seed", [20261015, 20261016])
def test_ninety_day_reference_benchmark_meets_declared_gates(seed):
    benchmark = generate_benchmark(seed)
    expected_digest = {
        20261015: "4533a170f07e361b9e9fc77528aa56822fb07fae58a00e1aa1cd7828ee00ad62",
        20261016: "414d813add890129a32d26af6ffe5ee444288eed261cc985de88dbd55ca66aee",
    }
    assert dataset_digest(benchmark) == expected_digest[seed]
    report = evaluate_results(benchmark, detect_anomalies(engineer_features(benchmark.records)))
    print(json.dumps(report, indent=2))
    assert report["status"] == "PASS", report
    assert all(row["detected"] >= 8 for row in report["by_scenario"].values())
