from uuid import uuid4

from sawakli.data.staging import staged_row_from_csv_dict


def test_staged_row_from_csv_dict() -> None:
    organization_id = uuid4()
    data_source_id = uuid4()

    parsed_row = {
        "date": "2026-08-30",
        "campaign_name": "Summer Campaign",
        "platform": "meta",
        "spend": 125.5,
        "impressions": 10000,
        "clicks": 500,
        "conversions": 25,
        "revenue": 500.0,
        "sessions": 450,
        "bounces": 50,
    }

    result = staged_row_from_csv_dict(
        organization_id,
        data_source_id,
        parsed_row,
    )

    assert result.organization_id == organization_id
    assert result.data_source_id == data_source_id
    assert result.provider == "csv_demo"
    assert result.external_id is None
    assert result.campaign_name == "Summer Campaign"
    assert result.platform_raw == "meta"
    assert result.objective is None
    assert result.status_raw is None
    assert result.budget is None
    assert result.start_date_raw == "2026-08-30"
    assert result.end_date_raw is None
    assert result.ad_group is None

    assert parsed_row["campaign_name"] == "Summer Campaign"
