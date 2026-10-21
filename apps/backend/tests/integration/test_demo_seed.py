"""QA-00: the demo-login seed is idempotent and logs in to Nour Fashion Co."""

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from sawakli.core.security import verify_password
from sawakli.db.models.organization import Organization
from sawakli.db.models.organization_member import OrganizationMember
from sawakli.db.models.user import User
from tests.conftest import auth_header, login_user
from tests.fixtures import seed as demo_seed

# Synthetic, test-only value; never a real credential.
TEST_PASSWORD = "qa00-synthetic-demo-password-not-secret"


@pytest.fixture()
def nour_org(db_session: Session) -> Generator[None, None, None]:
    # Migration 0009 inserts this organization, but the shared `client` fixture teardown deletes
    # every organization, so re-insert the row when an earlier test removed it.
    db_session.execute(
        text(
            "INSERT INTO organizations (id, name, plan) VALUES (:id, 'Nour Fashion Co.', 'demo') "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": demo_seed.DEMO_ORGANIZATION_ID},
    )
    db_session.commit()
    yield
    user_ids = select(User.id).where(func.lower(User.email) == demo_seed.DEMO_EMAIL)
    db_session.execute(delete(OrganizationMember).where(OrganizationMember.user_id.in_(user_ids)))
    db_session.execute(delete(User).where(func.lower(User.email) == demo_seed.DEMO_EMAIL))
    db_session.commit()


def _demo_rows(db_session: Session) -> tuple[int, list[tuple[object, str]]]:
    users = db_session.scalar(
        select(func.count()).select_from(User).where(User.email == demo_seed.DEMO_EMAIL)
    )
    memberships = db_session.execute(
        select(OrganizationMember.organization_id, OrganizationMember.role)
        .join(User, User.id == OrganizationMember.user_id)
        .where(User.email == demo_seed.DEMO_EMAIL)
    ).all()
    return int(users or 0), [tuple(row) for row in memberships]


def test_seed_twice_is_idempotent_and_links_only_nour(db_session: Session, nour_org: None) -> None:
    assert demo_seed.seed(db_session, TEST_PASSWORD) is True
    first = _demo_rows(db_session)
    hashed = db_session.scalar(
        select(User.hashed_password).where(User.email == demo_seed.DEMO_EMAIL)
    )

    assert demo_seed.seed(db_session, TEST_PASSWORD) is False
    second = _demo_rows(db_session)

    assert first == second == (1, [(demo_seed.DEMO_ORGANIZATION_ID, "owner")])
    assert (
        db_session.scalar(select(User.hashed_password).where(User.email == demo_seed.DEMO_EMAIL))
        == hashed
    )
    assert hashed is not None and hashed != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, hashed)


def test_seed_refuses_without_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(demo_seed.PASSWORD_ENV, raising=False)
    assert demo_seed.main() == 2
    assert demo_seed.PASSWORD_ENV in capsys.readouterr().err


def test_seed_refuses_password_with_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # LoginRequest strips the password, so a padded seed password could never log in.
    monkeypatch.setenv(demo_seed.PASSWORD_ENV, f" {TEST_PASSWORD} ")
    assert demo_seed.main() == 2
    err = capsys.readouterr().err
    assert "whitespace" in err
    assert TEST_PASSWORD not in err


def test_seed_refuses_when_demo_org_missing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(demo_seed, "DEMO_ORGANIZATION_ID", uuid4())
    with pytest.raises(demo_seed.SeedError, match="not found"):
        demo_seed.seed(db_session, TEST_PASSWORD)
    assert _demo_rows(db_session) == (0, [])


def test_seed_refuses_demo_user_in_another_org(db_session: Session, nour_org: None) -> None:
    demo_seed.seed(db_session, TEST_PASSWORD)
    other_org = Organization(name="QA-00 other org", plan="free")
    db_session.add(other_org)
    db_session.flush()
    user_id = db_session.scalar(select(User.id).where(User.email == demo_seed.DEMO_EMAIL))
    db_session.add(OrganizationMember(user_id=user_id, organization_id=other_org.id, role="member"))
    db_session.commit()
    try:
        with pytest.raises(demo_seed.SeedError, match="other organization"):
            demo_seed.seed(db_session, TEST_PASSWORD)
    finally:
        db_session.execute(
            delete(OrganizationMember).where(OrganizationMember.organization_id == other_org.id)
        )
        db_session.execute(delete(Organization).where(Organization.id == other_org.id))
        db_session.commit()


def test_seeded_demo_user_logs_in_to_nour(
    client: TestClient, db_session: Session, nour_org: None
) -> None:
    demo_seed.seed(db_session, TEST_PASSWORD)

    token = login_user(client, email=demo_seed.DEMO_EMAIL, password=TEST_PASSWORD)["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(str(token)))

    assert me.status_code == 200, me.text
    assert me.json()["organization"] == {
        "id": str(demo_seed.DEMO_ORGANIZATION_ID),
        "name": "Nour Fashion Co.",
    }
    assert me.json()["user"]["email"] == demo_seed.DEMO_EMAIL
