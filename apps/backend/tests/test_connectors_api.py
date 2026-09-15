from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from sawakli.api.main import app
from sawakli.api.routes.connectors import get_token_exchanger
from sawakli.connectors.oauth import ExchangedToken, Provider
from tests.conftest import auth_header, login_user, register_user

_VALID_CSV = """\
date,campaign_name,platform,spend,impressions,clicks,conversions,revenue,sessions,bounces
2026-09-01,Test Campaign,google,100.50,1000,50,10,250.00,200,20
"""

_INVALID_HEADER_CSV = """\
date,campaign_name,platform,spend
2026-09-01,Test Campaign,google,100
"""


def _create_user_and_token(
    client: TestClient,
    *,
    name: str,
    email: str,
    organization_name: str,
) -> str:
    register_user(
        client,
        name=name,
        email=email,
        password="Password123!",
        organization_name=organization_name,
    )

    login = login_user(
        client,
        email=email,
        password="Password123!",
    )

    return str(login["access_token"])


def test_connector_setup_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/connectors/setup")

    assert response.status_code == 401


def test_connector_setup_creates_csv_data_source(client: TestClient) -> None:
    token = _create_user_and_token(
        client,
        name="Connector User",
        email="connector@example.com",
        organization_name="Connector Org",
    )

    response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert response.status_code == 201

    payload: dict[str, Any] = response.json()

    assert payload["provider"] == "csv_demo"
    assert payload["status"] == "disconnected"
    assert payload["data_source_id"]


def test_csv_upload_parses_valid_file(client: TestClient) -> None:
    token = _create_user_and_token(
        client,
        name="CSV User",
        email="csv@example.com",
        organization_name="CSV Org",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    response = client.post(
        f"/api/connectors/csv/{data_source_id}/upload",
        headers=auth_header(token),
        files={
            "file": (
                "campaigns.csv",
                _VALID_CSV.encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    payload: dict[str, Any] = response.json()

    assert payload["data_source_id"] == data_source_id
    assert payload["provider"] == "csv_demo"
    assert payload["row_count"] == 1
    assert len(payload["parsed_rows"]) == 1
    assert payload["parse_warnings"] == []


def test_csv_upload_returns_parser_warnings(client: TestClient) -> None:
    token = _create_user_and_token(
        client,
        name="Warning User",
        email="warning@example.com",
        organization_name="Warning Org",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    csv_content = _VALID_CSV + ("2026-09-02,Bad Campaign,google,-10,1000,50,10,250,200,20\n")

    response = client.post(
        f"/api/connectors/csv/{data_source_id}/upload",
        headers=auth_header(token),
        files={
            "file": (
                "campaigns.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200

    payload: dict[str, Any] = response.json()

    assert payload["row_count"] == 1
    assert len(payload["parse_warnings"]) == 1
    assert "Row 3" in payload["parse_warnings"][0]


def test_csv_upload_rejects_invalid_file_safely(client: TestClient) -> None:
    token = _create_user_and_token(
        client,
        name="Invalid User",
        email="invalid@example.com",
        organization_name="Invalid Org",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    response = client.post(
        f"/api/connectors/csv/{data_source_id}/upload",
        headers=auth_header(token),
        files={
            "file": (
                "bad.csv",
                _INVALID_HEADER_CSV.encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 422

    payload: dict[str, Any] = response.json()

    assert payload["detail"]["code"] == "invalid_header"
    assert payload["detail"]["retryable"] is False
    assert "missing required column" in payload["detail"]["message"].lower()

    # Internal ConnectorError.message must never reach the UI.
    assert "Missing required column(s):" not in response.text


def test_csv_upload_rejects_connector_from_another_org(
    client: TestClient,
) -> None:
    user_a_token = _create_user_and_token(
        client,
        name="User A",
        email="user-a@example.com",
        organization_name="Org A",
    )

    user_b_token = _create_user_and_token(
        client,
        name="User B",
        email="user-b@example.com",
        organization_name="Org B",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(user_b_token),
    )

    assert setup_response.status_code == 201

    org_b_data_source_id = setup_response.json()["data_source_id"]

    response = client.post(
        f"/api/connectors/csv/{org_b_data_source_id}/upload",
        headers=auth_header(user_a_token),
        files={
            "file": (
                "campaigns.csv",
                _VALID_CSV.encode("utf-8"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 404


def test_connector_status_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get("/api/connectors/00000000-0000-0000-0000-000000000000/status")

    assert response.status_code == 401


def test_connector_status_without_token_is_not_connected(
    client: TestClient,
) -> None:
    token = _create_user_and_token(
        client,
        name="Status User",
        email="status@example.com",
        organization_name="Status Org",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    response = client.get(
        f"/api/connectors/{data_source_id}/status",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    payload: dict[str, Any] = response.json()

    assert payload["data_source_id"] == data_source_id
    assert payload["connected"] is False
    assert payload["token_valid"] is False
    assert payload["last_successful_call_at"] is None

    assert "access_token" not in response.text
    assert "refresh_token" not in response.text


def test_connector_status_rejects_cross_org_access(
    client: TestClient,
) -> None:
    user_a_token = _create_user_and_token(
        client,
        name="Status User A",
        email="status-a@example.com",
        organization_name="Status Org A",
    )

    user_b_token = _create_user_and_token(
        client,
        name="Status User B",
        email="status-b@example.com",
        organization_name="Status Org B",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(user_b_token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    response = client.get(
        f"/api/connectors/{data_source_id}/status",
        headers=auth_header(user_a_token),
    )

    assert response.status_code == 404


class FakeApiExchanger:
    """Test double for the CONN-02 TokenExchanger boundary."""

    def __init__(self) -> None:
        self.auth_code: str | None = None

    def exchange_auth_code(
        self,
        provider: Provider,
        auth_code: str,
    ) -> ExchangedToken:
        self.auth_code = auth_code

        return ExchangedToken(
            access_token="secret-access-token",
            refresh_token="secret-refresh-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def exchange_refresh_token(
        self,
        provider: Provider,
        refresh_token: str,
    ) -> ExchangedToken:
        raise AssertionError("refresh_token must not be called by the callback endpoint")


def test_oauth_callback_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/connectors/00000000-0000-0000-0000-000000000000/oauth/callback",
        json={
            "provider": "googleads",
            "code": "authorization-code",
        },
    )

    assert response.status_code == 401


def test_oauth_callback_rejects_cross_org_access(
    client: TestClient,
) -> None:
    user_a_token = _create_user_and_token(
        client,
        name="OAuth User A",
        email="oauth-a@example.com",
        organization_name="OAuth Org A",
    )

    user_b_token = _create_user_and_token(
        client,
        name="OAuth User B",
        email="oauth-b@example.com",
        organization_name="OAuth Org B",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(user_b_token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    response = client.post(
        f"/api/connectors/{data_source_id}/oauth/callback",
        headers=auth_header(user_a_token),
        json={
            "provider": "googleads",
            "code": "authorization-code",
        },
    )

    assert response.status_code == 404


def test_oauth_callback_rejects_provider_mismatch(
    client: TestClient,
) -> None:
    token = _create_user_and_token(
        client,
        name="OAuth Mismatch User",
        email="oauth-mismatch@example.com",
        organization_name="OAuth Mismatch Org",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    # The setup endpoint creates csv_demo; sending googleads must be rejected.
    fake_exchanger = FakeApiExchanger()
    app.dependency_overrides[get_token_exchanger] = lambda: fake_exchanger

    try:
        response = client.post(
            f"/api/connectors/{data_source_id}/oauth/callback",
            headers=auth_header(token),
            json={
                "provider": "googleads",
                "code": "authorization-code",
            },
        )
    finally:
        app.dependency_overrides.pop(get_token_exchanger, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "Provider does not match connector"
    assert fake_exchanger.auth_code is None


def test_oauth_callback_handoffs_code_without_exposing_tokens(
    client: TestClient,
) -> None:
    token = _create_user_and_token(
        client,
        name="OAuth User",
        email="oauth@example.com",
        organization_name="OAuth Org",
    )

    setup_response = client.post(
        "/api/connectors/setup",
        headers=auth_header(token),
    )

    assert setup_response.status_code == 201

    data_source_id = setup_response.json()["data_source_id"]

    # Turn the test source into a Google Ads connector.
    from sawakli.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                UPDATE data_sources
                SET provider = 'googleads'
                WHERE id = :data_source_id
                """
            ),
            {"data_source_id": data_source_id},
        )
        db.commit()
    finally:
        db.close()

    fake_exchanger = FakeApiExchanger()
    app.dependency_overrides[get_token_exchanger] = lambda: fake_exchanger

    try:
        response = client.post(
            f"/api/connectors/{data_source_id}/oauth/callback",
            headers=auth_header(token),
            json={
                "provider": "googleads",
                "code": "authorization-code-123",
            },
        )
    finally:
        app.dependency_overrides.pop(get_token_exchanger, None)

    assert response.status_code == 200

    assert fake_exchanger.auth_code == "authorization-code-123"

    payload: dict[str, Any] = response.json()

    assert payload["data_source_id"] == data_source_id
    assert payload["provider"] == "googleads"
    assert payload["status"] == "connected"

    # OAuth code and actual token values must never reach the UI.
    assert "authorization-code-123" not in response.text
    assert "secret-access-token" not in response.text
    assert "secret-refresh-token" not in response.text
