"""Versioned AI-02 reference benchmark; ground truth comes from interventions.

This is a new synthetic benchmark, not recovered DATA-02/Nour ground truth.
Generation never imports the detector or inspects its predictions. Every date is
explicitly clean or inside an injected event; no warm-up dates are excluded.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from random import Random
from typing import TYPE_CHECKING
from uuid import UUID

from sawakli.ai.features import MetricRecord

if TYPE_CHECKING:
    from sawakli.ai.anomaly.detector import AnomalyResult

BENCHMARK_VERSION = "ai02-reference-v1"
BENCHMARK_SEED = 20261015
FLAG_THRESHOLD = Decimal("0.80")  # Existing critical-severity boundary, fixed before evaluation.
DAYS = 90
CAMPAIGNS = 60
FIRST_DATE = date(2026, 1, 1)
SCENARIOS = ("spend_waste", "ctr_drop", "improvement")
Key = tuple[UUID, UUID, date]


@dataclass(frozen=True, slots=True)
class SeededEvent:
    organization_id: UUID
    campaign_id: UUID
    scenario: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class Benchmark:
    records: tuple[MetricRecord, ...]
    events: tuple[SeededEvent, ...]
    clean_keys: frozenset[Key]
    clean_campaigns: frozenset[tuple[UUID, UUID]]
    seed: int = BENCHMARK_SEED


def record_key(record: MetricRecord | AnomalyResult) -> Key:
    return record.organization_id, record.campaign_id, record.date


def generate_benchmark(seed: int = BENCHMARK_SEED) -> Benchmark:
    """Generate heterogeneous baselines and independently scheduled 3/5/7-day events."""
    records: list[MetricRecord] = []
    events: list[SeededEvent] = []
    clean_keys: set[Key] = set()
    clean_campaigns: set[tuple[UUID, UUID]] = set()
    weekly = (100, 104, 108, 103, 99, 88, 85)
    for campaign_number in range(1, CAMPAIGNS + 1):
        rng = Random(seed + campaign_number * 1009)
        organization_id = UUID(int=1 + (campaign_number - 1) // 20)
        campaign_id = UUID(int=1000 + campaign_number)
        scenario = "clean" if campaign_number <= 30 else SCENARIOS[(campaign_number - 31) % 3]
        start_offset = 35 + ((campaign_number * 7) % 35)
        duration = (3, 5, 7)[(campaign_number // 3) % 3]
        start, end = (
            FIRST_DATE + timedelta(days=start_offset),
            FIRST_DATE + timedelta(days=start_offset + duration - 1),
        )
        if scenario == "clean":
            clean_campaigns.add((organization_id, campaign_id))
        else:
            events.append(SeededEvent(organization_id, campaign_id, scenario, start, end))

        scale = 1 + campaign_number % 5
        for offset in range(DAYS):
            current_date = FIRST_DATE + timedelta(days=offset)
            # Integer arithmetic makes the generated facts independent of NumPy/sklearn versions.
            factor = weekly[(offset + campaign_number) % 7]
            spend = Decimal(scale * factor * rng.randint(94, 106)) / Decimal(100)
            impressions = scale * factor * rng.randint(95, 105)
            ctr_basis_points = 200 + (campaign_number % 4) * 60 + rng.randint(-12, 12)
            clicks = impressions * ctr_basis_points // 10000
            conversions = max(1, clicks * (60 + rng.randint(-5, 5)) // 1000)
            revenue = spend * Decimal(280 + (campaign_number % 3) * 40 + rng.randint(-15, 15))
            revenue = (revenue / Decimal(100)).quantize(Decimal("0.01"))
            event_day = scenario != "clean" and start <= current_date <= end
            if event_day:
                if scenario == "spend_waste":
                    spend *= 3
                    revenue = (revenue / 3).quantize(Decimal("0.01"))
                elif scenario == "ctr_drop":
                    clicks = max(1, clicks // 5)
                    conversions = max(1, conversions // 5)
                    revenue = (revenue / 5).quantize(Decimal("0.01"))
                else:
                    conversions *= 3
                    revenue *= 3
            record = MetricRecord(
                organization_id=organization_id,
                campaign_id=campaign_id,
                campaign_name=f"Reference {campaign_number:02d} {scenario}",
                platform="meta" if campaign_number % 2 else "google",
                date=current_date,
                spend=spend,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                revenue=revenue,
            )
            records.append(record)
            if not event_day:
                clean_keys.add(record_key(record))
    return Benchmark(
        tuple(records), tuple(events), frozenset(clean_keys), frozenset(clean_campaigns), seed
    )


def dataset_digest(benchmark: Benchmark) -> str:
    """Identify the exact source facts, independent of model outputs."""
    rows = [
        [
            str(value)
            for value in (
                r.organization_id,
                r.campaign_id,
                r.campaign_name,
                r.platform,
                r.date,
                r.spend,
                r.impressions,
                r.clicks,
                r.conversions,
                r.revenue,
            )
        ]
        for r in benchmark.records
    ]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def evaluate_results(benchmark: Benchmark, results: Sequence[AnomalyResult]) -> dict[str, object]:
    """Evaluate all rows, exact interval matches, and an explicit campaign FPR denominator."""
    expected = {record_key(record) for record in benchmark.records}
    actual = [record_key(result) for result in results]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("results must contain exactly one result for every benchmark campaign-day")
    flagged = {record_key(result) for result in results if result.score >= FLAG_THRESHOLD}
    positive = expected - benchmark.clean_keys
    true_positive_days = len(flagged & positive)
    false_positive_days = len(flagged & benchmark.clean_keys)
    detected = [
        event
        for event in benchmark.events
        if any(
            org == event.organization_id
            and campaign == event.campaign_id
            and event.start <= day <= event.end
            for org, campaign, day in flagged
        )
    ]
    false_positive_campaigns = len(
        {
            (org, campaign)
            for org, campaign, _ in flagged
            if (org, campaign) in benchmark.clean_campaigns
        }
    )
    event_recall = Decimal(len(detected)) / len(benchmark.events)
    day_recall = Decimal(true_positive_days) / len(positive)
    clean_day_fpr = Decimal(false_positive_days) / len(benchmark.clean_keys)
    clean_campaign_fpr = Decimal(false_positive_campaigns) / len(benchmark.clean_campaigns)
    return {
        "benchmark": BENCHMARK_VERSION,
        "seed": benchmark.seed,
        "dataset_sha256": dataset_digest(benchmark),
        "rows": len(expected),
        "flag_threshold": str(FLAG_THRESHOLD),
        "evaluation_mode": "retrospective batch; not an online or held-out forecast test",
        "warmup_exclusions": 0,
        "events": len(benchmark.events),
        "detected_events": len(detected),
        "event_recall": str(event_recall),
        "anomaly_days": len(positive),
        "detected_anomaly_days": true_positive_days,
        "day_recall": str(day_recall),
        "clean_days": len(benchmark.clean_keys),
        "false_positive_days": false_positive_days,
        "clean_day_fpr": str(clean_day_fpr),
        "clean_campaigns": len(benchmark.clean_campaigns),
        "false_positive_campaigns": false_positive_campaigns,
        "clean_campaign_fpr": str(clean_campaign_fpr),
        "by_scenario": {
            scenario: {
                "events": sum(e.scenario == scenario for e in benchmark.events),
                "detected": sum(e.scenario == scenario for e in detected),
            }
            for scenario in SCENARIOS
        },
        "status": "PASS"
        if (
            min(event_recall, day_recall) >= Decimal("0.80")
            and max(clean_day_fpr, clean_campaign_fpr) <= Decimal("0.05")
        )
        else "FAIL",
    }
