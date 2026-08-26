from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.conftest import login_user, register_user


def test_register_creates_user_and_organization(client: TestClient) -> None:
    payload = register_user(
        client,
        name="Ada Lovelace",
        email="ada@example.com",
        password="correct-password",
        organization_name="Analytical Engines",
    )

    user = payload["user"]
    organization = payload["organization"]
    assert isinstance(user, dict)
    assert isinstance(organization, dict)
    assert user["name"] == "Ada Lovelace"
    assert user["email"] == "ada@example.com"
    assert "hashed_password" not in user
    assert "password" not in payload
    assert organization["name"] == "Analytical Engines"


def test_register_requires_name(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "name": "   ",
            "email": "nameless@example.com",
            "password": "correct-password",
            "organization_name": "No Name Org",
        },
    )
    assert response.status_code == 422


def test_register_duplicate_email_returns_409(client: TestClient, db_session: Session) -> None:
    from sawakli.db.models.organization import Organization
    from sawakli.db.models.organization_member import OrganizationMember
    from sawakli.db.models.user import User

    register_user(
        client,
        name="Ada Lovelace",
        email="ada@example.com",
        password="correct-password",
        organization_name="Analytical Engines",
    )

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Ada Clone",
            "email": "ada@example.com",
            "password": "other-password",
            "organization_name": "Clone Org",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"

    user_count = db_session.scalar(select(func.count()).select_from(User))
    org_count = db_session.scalar(select(func.count()).select_from(Organization))
    member_count = db_session.scalar(select(func.count()).select_from(OrganizationMember))
    assert user_count == 1
    assert org_count == 1
    assert member_count == 1


def test_login_returns_token_for_valid_credentials(client: TestClient) -> None:
    register_user(
        client,
        name="Ada Lovelace",
        email="ada@example.com",
        password="correct-password",
        organization_name="Analytical Engines",
    )
    payload = login_user(client, email="ada@example.com", password="correct-password")

    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["access_token"]
    user = payload["user"]
    assert isinstance(user, dict)
    assert user["email"] == "ada@example.com"
    assert user["name"] == "Ada Lovelace"
    assert "hashed_password" not in user


def test_login_wrong_password_is_rejected(client: TestClient) -> None:
    register_user(
        client,
        name="Ada Lovelace",
        email="ada@example.com",
        password="correct-password",
        organization_name="Analytical Engines",
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "ada@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_uses_same_message(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "any-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
