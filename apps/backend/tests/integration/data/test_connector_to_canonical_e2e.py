import csv
import io
import json
from uuid import uuid4

import sqlalchemy as sa

from sawakli.connectors.csv import RawResponse, parse_csv_upload
from sawakli.data.normalization.pipeline import normalize_and_upsert_batch
from sawakli.data.staging.adapters import staged_row_from_csv_dict


def _csv_fixture() -> str:
    rows = [
        {
            "date": "2026-08-29",
            "campaign_name": "Summer Campaign",
            "platform": "meta",
            "spend": "100.00",
            "impressions": "1000",
            "clicks": "100",
            "conversions": "10",
            "revenue": "200.00",
            "sessions": "500",
            "bounces": "100",
        },
        {
            "date": "2026-08-30",
            "campaign_name": "Summer Campaign",
            "platform": "meta",
            "spend": "50.00",
            "impressions": "500",
            "clicks": "50",
            "conversions": "5",
            "revenue": "100.00",
            "sessions": "300",
            "bounces": "60",
        },
        {
            "date": "2026-08-29",
            "campaign_name": "Search Campaign",
            "platform": "google",
            "spend": "75.00",
            "impressions": "750",
            "clicks": "75",
            "conversions": "8",
            "revenue": "150.00",
            "sessions": "400",
            "bounces": "80",
        },
        {
            "date": "2026-08-29",
            "campaign_name": "Summer Campaign",
            "platform": "meta",
            "spend": "100.00",
            "impressions": "1000",
            "clicks": "100",
            "conversions": "10",
            "revenue": "200.00",
            "sessions": "500",
            "bounces": "100",
        },
        {
            "date": "2026-08-31",
            "campaign_name": "Broken Campaign",
            "platform": "meta",
            "spend": "not-a-number",
            "impressions": "100",
            "clicks": "10",
            "conversions": "1",
            "revenue": "10.00",
            "sessions": "20",
            "bounces": "2",
        },
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def test_csv_connector_reaches_canonical_facts_with_reconciliation(
    db_session,
) -> None:
    organization_id = uuid4()
    data_source_id = uuid4()
    upload_id = uuid4()
    csv_text = _csv_fixture()

    db_session.execute(
        sa.text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
        {"id": organization_id, "name": "QA-02 E2E Organization"},
    )
    db_session.execute(
        sa.text(
            "INSERT INTO data_sources (id, organization_id, provider, status) "
            "VALUES (:id, :organization_id, 'csv_demo', 'demo_data')"
        ),
        {"id": data_source_id, "organization_id": organization_id},
    )
    db_session.execute(
        sa.text(
            "INSERT INTO raw_api_responses "
            "(id, data_source_id, provider, endpoint, payload, fetched_at) "
            "VALUES (:id, :data_source_id, 'csv_demo', :endpoint, CAST(:payload AS jsonb), "
            "CURRENT_TIMESTAMP)"
        ),
        {
            "id": upload_id,
            "data_source_id": data_source_id,
            "endpoint": "csv://qa-02/seed.csv",
            "payload": json.dumps({"csv": csv_text}),
        },
    )
    db_session.commit()

    parsed = parse_csv_upload(io.BytesIO(csv_text.encode()), organization_id, upload_id)

    assert isinstance(parsed, RawResponse)
    assert parsed.row_count == 4
    assert len(parsed.parse_warnings) == 1
    assert "not a valid number" in parsed.parse_warnings[0]

    staged_rows = [
        staged_row_from_csv_dict(organization_id, data_source_id, row) for row in parsed.parsed_rows
    ]
    first_import = normalize_and_upsert_batch(db_session, staged_rows)
    second_import = normalize_and_upsert_batch(db_session, staged_rows)
    db_session.commit()

    campaign_count = db_session.scalar(
        sa.text("SELECT COUNT(*) FROM campaigns WHERE organization_id = :organization_id"),
        {"organization_id": organization_id},
    )
    daily_count = db_session.scalar(
        sa.text("SELECT COUNT(*) FROM daily_metrics WHERE organization_id = :organization_id"),
        {"organization_id": organization_id},
    )
    ga_count = db_session.scalar(
        sa.text("SELECT COUNT(*) FROM ga_events WHERE organization_id = :organization_id"),
        {"organization_id": organization_id},
    )
    raw_count = db_session.scalar(
        sa.text("SELECT COUNT(*) FROM raw_api_responses WHERE data_source_id = :data_source_id"),
        {"data_source_id": data_source_id},
    )
    totals = db_session.execute(
        sa.text(
            "SELECT COALESCE(SUM(spend), 0), COALESCE(SUM(impressions), 0), "
            "COALESCE(SUM(clicks), 0), COALESCE(SUM(conversions), 0), "
            "COALESCE(SUM(revenue), 0) FROM daily_metrics "
            "WHERE organization_id = :organization_id"
        ),
        {"organization_id": organization_id},
    ).one()
    ga_totals = db_session.execute(
        sa.text(
            "SELECT COALESCE(SUM(sessions), 0), COALESCE(SUM(bounces), 0) FROM ga_events "
            "WHERE organization_id = :organization_id"
        ),
        {"organization_id": organization_id},
    ).one()

    assert campaign_count == 2
    assert daily_count == 3
    assert ga_count == 3
    assert raw_count == 1
    assert totals == (225, 2250, 225, 23, 450)
    assert ga_totals == (1200, 240)
    assert [result.campaign_id for result in first_import.results] == [
        result.campaign_id for result in second_import.results
    ]

    db_session.execute(
        sa.text("DELETE FROM organizations WHERE id = :organization_id"),
        {"organization_id": organization_id},
    )
    db_session.commit()
