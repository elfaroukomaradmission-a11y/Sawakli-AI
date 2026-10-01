from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import auth_header, login_user, register_user

_VALID_CSV = (
    "date,campaign_name,platform,spend,impressions,clicks,conversions,revenue,sessions,bounces\n"
    "2026-08-29,Summer Campaign,meta,100,1000,100,10,200,500,100\n"
)
_INVALID_HEADER_CSV = "date,campaign_name,platform\n2026-08-29,Broken,meta\n"


def _count(sql: str, **params: Any) -> int:
    from sawakli.db.session import SessionLocal

    db = SessionLocal()
    try:
        return int(db.execute(text(sql), params).scalar_one())
    finally:
        db.close()


def _token(client: TestClient, email: str, organization_name: str) -> str:
    register_user(
        client,
        name="Connector User",
        email=email,
        password="Synthetic-Password-123",
        organization_name=organization_name,
    )
    return str(login_user(client, email=email, password="Synthetic-Password-123")["access_token"])


def test_csv_upload_writes_raw_canonical_and_source_status(client: TestClient) -> None:
    token = _token(client, "handoff@example.test", "Handoff Organization")
    source = client.post("/api/connectors/setup", headers=auth_header(token))
    assert source.status_code == 201, source.text
    data_source_id = source.json()["data_source_id"]

    response = client.post(
        f"/api/connectors/csv/{data_source_id}/upload",
        headers=auth_header(token),
        files={"file": ("campaigns.csv", _VALID_CSV.encode(), "text/csv")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["sync_status"] == "success"
    assert response.json()["last_synced_at"] is not None
    assert response.json()["row_count"] == 1
    assert (
        _count(
            "SELECT COUNT(*) FROM raw_api_responses WHERE data_source_id = :id",
            id=data_source_id,
        )
        == 1
    )
    assert (
        _count(
            "SELECT COUNT(*) FROM campaigns WHERE data_source_id = :id",
            id=data_source_id,
        )
        == 1
    )
    assert (
        _count(
            "SELECT COUNT(*) FROM daily_metrics WHERE campaign_id IN "
            "(SELECT id FROM campaigns WHERE data_source_id = :id)",
            id=data_source_id,
        )
        == 1
    )
    assert (
        _count(
            "SELECT COUNT(*) FROM ga_events WHERE campaign_id IN "
            "(SELECT id FROM campaigns WHERE data_source_id = :id)",
            id=data_source_id,
        )
        == 1
    )


def test_invalid_csv_marks_source_failed_without_canonical_rows(client: TestClient) -> None:
    token = _token(client, "failure@example.test", "Failure Organization")
    source = client.post("/api/connectors/setup", headers=auth_header(token))
    assert source.status_code == 201, source.text
    data_source_id = source.json()["data_source_id"]

    response = client.post(
        f"/api/connectors/csv/{data_source_id}/upload",
        headers=auth_header(token),
        files={"file": ("bad.csv", _INVALID_HEADER_CSV.encode(), "text/csv")},
    )

    assert response.status_code == 422
    assert (
        _count(
            "SELECT COUNT(*) FROM raw_api_responses WHERE data_source_id = :id",
            id=data_source_id,
        )
        == 0
    )
    assert (
        _count(
            "SELECT COUNT(*) FROM data_sources "
            "WHERE id = :id AND sync_status = 'failed' AND last_error IS NOT NULL",
            id=data_source_id,
        )
        == 1
    )
