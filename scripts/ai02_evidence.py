"""Trace all 360 committed Nour seed rows without requiring PostgreSQL.

This evidence-only reader parses the migration's literal SQL; it executes no SQL
or migration code and is not a production loader. The source has no day labels.

Run from the repository root:
PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python scripts/ai02_evidence.py
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sawakli.ai.anomaly.detector import AnomalyResult, detect_anomalies
from sawakli.ai.features import MetricRecord, engineer_features

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = REPO_ROOT / "apps/backend/alembic/versions/0009_seed_demo_data.py"
CAMPAIGNS = {
    "a": ("Summer Collection Push", "meta"),
    "b": ("Winter Pre-Launch", "google"),
    "c": ("Flash Sale Banner", "meta"),
    "d": ("Evergreen Basics", "google"),
}


def load_committed_seed() -> tuple[MetricRecord, ...]:
    """Read the existing daily_metrics VALUES block without running a migration."""
    module = ast.parse(SEED_PATH.read_text())
    sql = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_UPGRADE_SQL" for target in node.targets
        )
    )
    values_block = sql.split("INSERT INTO daily_metrics ", 1)[1].split("ON CONFLICT", 1)[0]
    matches = re.findall(
        r"\('([^']+)', '([^']+)', '([^']+)', ([\d.]+), (\d+), (\d+), (\d+), ([\d.]+)\)",
        values_block,
    )
    if len(matches) != 360:
        raise ValueError("Expected the 360-row Nour seed; inspect changed source format")
    records = []
    for org, campaign, day, spend, impressions, clicks, conversions, revenue in matches:
        name, platform = CAMPAIGNS[campaign[-1]]
        records.append(
            MetricRecord(
                organization_id=UUID(org),
                campaign_id=UUID(campaign),
                campaign_name=name,
                platform=platform,
                date=date.fromisoformat(day),
                spend=Decimal(spend),
                impressions=int(impressions),
                clicks=int(clicks),
                conversions=int(conversions),
                revenue=Decimal(revenue),
            )
        )
    return tuple(records)


def main() -> None:
    results = detect_anomalies(engineer_features(load_committed_seed()))
    campaigns: dict[str, list[AnomalyResult]] = defaultdict(list)
    for result in results:
        campaigns[result.campaign_name].append(result)
    print(
        json.dumps(
            {
                "source": str(SEED_PATH.relative_to(REPO_ROOT)),
                "rows": len(results),
                "quality_evaluation": "NOT RUN — approved campaign-day labels unavailable",
                "flag_threshold": "0.40 (diagnostic threshold from existing AI-02 fixture)",
                "campaigns": {
                    name: {
                        "days": len(rows),
                        "flagged_days": sum(row.score >= Decimal("0.4") for row in rows),
                        "maximum_score": str(max(row.score for row in rows)),
                        "latest_score": str(rows[-1].score),
                        "latest_direction": rows[-1].direction,
                    }
                    for name, rows in campaigns.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
