from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from sawakli.ai.features import CsvDataLoader, FeatureDataError, local_campaign_id

ORG_ID = UUID("10000000-0000-0000-0000-000000000001")
MAPPED_CAMPAIGN_ID = UUID("20000000-0000-0000-0000-000000000009")
HEADER = (
    "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue,sessions,bounces\n"
)


def write_csv(path: Path, rows: str, header: str = HEADER) -> Path:
    path.write_text(header + rows, encoding="utf-8")
    return path


def test_local_csv_loads_canonical_contract_and_stable_campaign_ids(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "metrics.csv",
        "2026-01-02,Campaign B,google,20.5,200,20,2,50,100,10\n"
        "2026-01-01,Campaign A,meta,10,100,10,1,30,50,5\n",
    )
    loader = CsvDataLoader(path)

    first = loader.load_metrics(ORG_ID)
    second = loader.load_metrics(ORG_ID)

    assert first == second
    campaign_a = next(row for row in first if row.campaign_name == "Campaign A")
    assert campaign_a.campaign_id == local_campaign_id(ORG_ID, "Campaign A", "meta")
    assert campaign_a.organization_id == ORG_ID
    assert campaign_a.date == date(2026, 1, 1)
    assert campaign_a.spend == Decimal("10")
    assert campaign_a.sessions == 50
    assert campaign_a.bounces == 5
    assert isinstance(campaign_a.impressions, int)


def test_local_csv_accepts_explicit_campaign_mapping_and_filters(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "metrics.csv",
        "2026-01-01,Campaign A,meta,10,100,10,1,30,50,5\n"
        "2026-01-02,Campaign A,meta,20,200,20,2,60,100,10\n",
    )
    loader = CsvDataLoader(path, campaign_id_map={("Campaign A", "meta"): MAPPED_CAMPAIGN_ID})

    result = loader.load_metrics(
        ORG_ID,
        campaign_ids=[MAPPED_CAMPAIGN_ID],
        date_from=date(2026, 1, 2),
        date_to=date(2026, 1, 2),
    )

    assert len(result) == 1
    assert result[0].campaign_id == MAPPED_CAMPAIGN_ID
    assert result[0].date == date(2026, 1, 2)


def test_local_csv_treats_missing_optional_analytics_as_missing(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "metrics.csv",
        "2026-01-01,Campaign A,meta,10,100,10,1,30\n",
        header="date,campaign_name,platform,spend,impressions,clicks,conversions,revenue\n",
    )

    result = CsvDataLoader(path).load_metrics(ORG_ID)

    assert result[0].sessions is None
    assert result[0].bounces is None


@pytest.mark.parametrize(
    "header, rows, message",
    [
        (
            "date,campaign_name,platform,spend,impressions,clicks,conversions\n",
            "2026-01-01,Campaign A,meta,10,100,10,1\n",
            "missing required columns: revenue",
        ),
        (HEADER, "bad-date,Campaign A,meta,10,100,10,1,30,50,5\n", "valid ISO date"),
        (HEADER, "2026-01-01,Campaign A,meta,nope,100,10,1,30,50,5\n", "numeric"),
        (HEADER, "2026-01-01,Campaign A,meta,-1,100,10,1,30,50,5\n", "non-negative"),
        (HEADER, "2026-01-01,Campaign A,meta,NaN,100,10,1,30,50,5\n", "finite"),
        (HEADER, "2026-01-01,Campaign A,meta,10,100,10,1,30,5,6\n", "cannot exceed"),
        (
            HEADER,
            "2026-01-01,Campaign A,meta,10,100,10,1,30,50,5\n"
            "2026-01-01,Campaign A,meta,11,110,11,1,31,51,5\n",
            "duplicate campaign/date",
        ),
    ],
)
def test_malformed_csv_is_rejected(tmp_path: Path, header: str, rows: str, message: str) -> None:
    path = write_csv(tmp_path / "bad.csv", rows, header=header)

    with pytest.raises(FeatureDataError, match=message):
        CsvDataLoader(path).load_metrics(ORG_ID)


def test_inverted_date_range_is_rejected(tmp_path: Path) -> None:
    path = write_csv(
        tmp_path / "metrics.csv",
        "2026-01-01,Campaign A,meta,10,100,10,1,30,50,5\n",
    )

    with pytest.raises(FeatureDataError, match="date_from"):
        CsvDataLoader(path).load_metrics(
            ORG_ID,
            date_from=date(2026, 1, 2),
            date_to=date(2026, 1, 1),
        )
