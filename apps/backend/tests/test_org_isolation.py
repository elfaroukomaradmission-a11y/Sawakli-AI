from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import Session

from sawakli.core.config import settings
from tests.conftest import auth_header, insert_job, login_user, register_user


def _register_and_login(
    client: TestClient, *, name: str, email: str, password: str, organization_name: str
) -> tuple[str, UUID]:
    registered = register_user(
        client,
        name=name,
        email=email,
        password=password,
        organization_name=organization_name,
    )
    organization = registered["organization"]
    assert isinstance(organization, dict)
    organization_id = UUID(str(organization["id"]))
    login_payload = login_user(client, email=email, password=password)
    token = login_payload["access_token"]
    assert isinstance(token, str)
    return token, organization_id


def test_protected_route_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_protected_route_rejects_broken_token(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers=auth_header("not-a-valid-token"))
    assert response.status_code == 401


def test_protected_route_rejects_expired_token(client: TestClient) -> None:
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "org_id": str(uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 401


def test_protected_route_returns_authenticated_org(client: TestClient) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Ada Lovelace",
        email="ada@example.com",
        password="correct-password",
        organization_name="Analytical Engines",
    )
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["organization"]["id"] == str(organization_id)
    assert "hashed_password" not in body["user"]


def test_org_isolation_hides_other_organizations_jobs(
    client: TestClient, db_session: Session
) -> None:
    token_a, org_a = _register_and_login(
        client,
        name="User A",
        email="a@example.com",
        password="password-a",
        organization_name="Org A",
    )
    token_b, org_b = _register_and_login(
        client,
        name="User B",
        email="b@example.com",
        password="password-b",
        organization_name="Org B",
    )

    job_a = insert_job(db_session, org_a)
    job_b = insert_job(db_session, org_b)

    response_a = client.get(
        "/api/jobs",
        headers=auth_header(token_a),
        params={"organization_id": str(org_b)},
    )
    assert response_a.status_code == 200
    ids_a = {item["id"] for item in response_a.json()}
    assert ids_a == {str(job_a)}
    assert str(job_b) not in ids_a

    response_b = client.get("/api/jobs", headers=auth_header(token_b))
    assert response_b.status_code == 200
    ids_b = {item["id"] for item in response_b.json()}
    assert ids_b == {str(job_b)}
    assert str(job_a) not in ids_b


def test_me_ignores_requested_foreign_organization_id(client: TestClient) -> None:
    token_a, org_a = _register_and_login(
        client,
        name="User A",
        email="a@example.com",
        password="password-a",
        organization_name="Org A",
    )
    _, org_b = _register_and_login(
        client,
        name="User B",
        email="b@example.com",
        password="password-b",
        organization_name="Org B",
    )

    response = client.get(
        "/api/auth/me",
        headers=auth_header(token_a),
        params={"organization_id": str(org_b)},
    )
    assert response.status_code == 200
    assert response.json()["organization"]["id"] == str(org_a)
