from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from sawakli.ai.features import CsvDataLoader, DatabaseDataLoader, MetricRecord

NOUR_ORG_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
NOUR_CAMPAIGN_ID = UUID("770e8400-e29b-41d4-a716-44665544000a")
TEST_ORG_ID = UUID("10000000-0000-0000-0000-000000000099")
TEST_DATA_SOURCE_ID = UUID("11000000-0000-0000-0000-000000000099")
TEST_CAMPAIGN_A = UUID("12000000-0000-0000-0000-000000000001")
TEST_CAMPAIGN_B = UUID("12000000-0000-0000-0000-000000000002")


def seed_test_metrics(db_session: Session) -> None:
    db_session.execute(
        text("INSERT INTO organizations (id, name) VALUES (:id, 'AI-01 Test Org')"),
        {"id": TEST_ORG_ID},
    )
    db_session.execute(
        text(
            "INSERT INTO data_sources (id, organization_id, provider) "
            "VALUES (:id, :organization_id, 'csv_demo')"
        ),
        {"id": TEST_DATA_SOURCE_ID, "organization_id": TEST_ORG_ID},
    )
    db_session.execute(
        text(
            "INSERT INTO campaigns (id, organization_id, data_source_id, name, platform) "
            "VALUES (:campaign_a, :organization_id, :data_source_id, 'A', 'meta'), "
            "(:campaign_b, :organization_id, :data_source_id, 'B', 'google')"
        ),
        {
            "campaign_a": TEST_CAMPAIGN_A,
            "campaign_b": TEST_CAMPAIGN_B,
            "organization_id": TEST_ORG_ID,
            "data_source_id": TEST_DATA_SOURCE_ID,
        },
    )
    db_session.execute(
        text(
            "INSERT INTO daily_metrics "
            "(organization_id, campaign_id, date, spend, impressions, clicks, "
            "conversions, revenue) "
            "VALUES "
            "(:organization_id, :campaign_b, '2026-01-02', 20, 200, 20, 2, 60), "
            "(:organization_id, :campaign_a, '2026-01-02', 11, 110, 11, 1, 31), "
            "(:organization_id, :campaign_a, '2026-01-01', 10, 100, 10, 1, 30)"
        ),
        {
            "organization_id": TEST_ORG_ID,
            "campaign_a": TEST_CAMPAIGN_A,
            "campaign_b": TEST_CAMPAIGN_B,
        },
    )


def test_seeded_nour_database_loads_all_campaign_days_in_order(
    db_session: Session,
) -> None:
    result = DatabaseDataLoader(db_session).load_metrics(NOUR_ORG_ID)

    assert len(result) == 360
    assert all(isinstance(row, MetricRecord) for row in result)
    assert all(row.organization_id == NOUR_ORG_ID for row in result)
    assert [(row.campaign_id.int, row.date) for row in result] == sorted(
        (row.campaign_id.int, row.date) for row in result
    )
    assert result[0].sessions is None
    assert result[0].bounces is None


def test_database_loader_is_org_scoped_and_campaign_filter_cannot_bypass_it(
    db_session: Session,
) -> None:
    seed_test_metrics(db_session)
    loader = DatabaseDataLoader(db_session)

    result = loader.load_metrics(
        TEST_ORG_ID,
        campaign_ids=[TEST_CAMPAIGN_A, NOUR_CAMPAIGN_ID],
    )
    foreign_result = loader.load_metrics(
        NOUR_ORG_ID,
        campaign_ids=[TEST_CAMPAIGN_A],
    )

    assert len(result) == 2
    assert {row.campaign_id for row in result} == {TEST_CAMPAIGN_A}
    assert all(row.organization_id == TEST_ORG_ID for row in result)
    assert foreign_result == ()


def test_database_output_is_deterministically_ordered_and_matches_local_types(
    db_session: Session,
    tmp_path: Path,
) -> None:
    seed_test_metrics(db_session)
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text(
        "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue\n"
        "2026-01-01,A,meta,10,100,10,1,30\n",
        encoding="utf-8",
    )

    result = DatabaseDataLoader(db_session).load_metrics(TEST_ORG_ID)
    local_result = CsvDataLoader(
        csv_path,
        campaign_id_map={("A", "meta"): TEST_CAMPAIGN_A},
    ).load_metrics(TEST_ORG_ID)

    assert [(row.campaign_id, row.date) for row in result] == [
        (TEST_CAMPAIGN_A, date(2026, 1, 1)),
        (TEST_CAMPAIGN_A, date(2026, 1, 2)),
        (TEST_CAMPAIGN_B, date(2026, 1, 2)),
    ]
    assert result[0].spend == Decimal("10")
    assert isinstance(result[0].impressions, int)
    assert isinstance(result[0], MetricRecord)
    assert result[0] == local_result[0]
