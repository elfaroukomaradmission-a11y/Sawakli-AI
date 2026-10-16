"""Replay AI-02's reference benchmark and optionally export all facts and labels.

From the repository root:
PYTHONPATH=apps/backend/src:apps/backend python scripts/ai02_benchmark.py
Add --export-dir /tmp/ai02-audit to export campaign_data.csv, labels.json and results.json.
Exit status is nonzero if any declared acceptance gate fails.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
from dataclasses import asdict
from pathlib import Path

import numpy
import sklearn

from sawakli.ai.anomaly.detector import detect_anomalies
from sawakli.ai.features import engineer_features
from tests.fixtures.ai02_benchmark import (
    BENCHMARK_SEED,
    BENCHMARK_VERSION,
    Benchmark,
    dataset_digest,
    evaluate_results,
    generate_benchmark,
)


def export_source(benchmark: Benchmark, directory: Path) -> None:
    """Write independently generated ground truth before any detector execution."""
    directory.mkdir(parents=True, exist_ok=True)
    fields = (
        "organization_id",
        "campaign_id",
        "campaign_name",
        "platform",
        "date",
        "spend",
        "impressions",
        "clicks",
        "conversions",
        "revenue",
    )
    with (directory / "campaign_data.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {field: str(getattr(r, field)) for field in fields} for r in benchmark.records
        )
    labels = {
        "benchmark": BENCHMARK_VERSION,
        "seed": benchmark.seed,
        "dataset_sha256": dataset_digest(benchmark),
        "provenance": "new reference generator; not historical DATA-02 labels",
        "events": [asdict(event) for event in benchmark.events],
        "clean_campaigns": sorted(benchmark.clean_campaigns),
        "clean_campaign_days": sorted(benchmark.clean_keys),
        "excluded_campaign_days": [],
    }
    (directory / "labels.json").write_text(json.dumps(labels, default=str, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path)
    parser.add_argument("--seed", type=int, default=BENCHMARK_SEED)
    args = parser.parse_args()
    benchmark = generate_benchmark(args.seed)
    if args.export_dir:
        export_source(benchmark, args.export_dir)
    report = evaluate_results(benchmark, detect_anomalies(engineer_features(benchmark.records)))
    report["runtime"] = {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scikit_learn": sklearn.__version__,
    }
    output = json.dumps(report, indent=2) + "\n"
    print(output, end="")
    if args.export_dir:
        (args.export_dir / "results.json").write_text(output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
