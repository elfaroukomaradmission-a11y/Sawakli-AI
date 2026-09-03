from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from tests.conftest import auth_header, insert_campaign, login_user, register_user


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


def test_refresh_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/analysis/refresh", json={})
    assert response.status_code == 401


def test_refresh_with_no_campaign_ids_creates_pending_job(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Nour Owner",
        email="nour@example.com",
        password="correct-password",
        organization_name="Nour Fashion Co.",
    )

    response = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "PENDING"
    job_id = UUID(body["job_id"])

    job = db_session.get(Job, job_id)
    assert job is not None
    assert job.organization_id == organization_id
    assert job.status == "PENDING"
    assert job.priority == "HIGH"
    assert job.campaign_ids is None
    assert job.model_run_id is None


def test_refresh_with_valid_campaign_ids_creates_job_scoped_to_them(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="owner@example.com",
        password="correct-password",
        organization_name="Org With Campaigns",
    )
    campaign_id = insert_campaign(db_session, organization_id)

    response = client.post(
        "/api/analysis/refresh",
        headers=auth_header(token),
        json={"campaign_ids": [str(campaign_id)]},
    )
    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])

    job = db_session.get(Job, job_id)
    assert job is not None
    assert job.campaign_ids == [str(campaign_id)]


def test_refresh_rejects_campaign_ids_from_another_organization(
    client: TestClient, db_session: Session
) -> None:
    token_a, org_a = _register_and_login(
        client,
        name="Org A Owner",
        email="a-owner@example.com",
        password="password-a",
        organization_name="Org A",
    )
    _, org_b = _register_and_login(
        client,
        name="Org B Owner",
        email="b-owner@example.com",
        password="password-b",
        organization_name="Org B",
    )
    foreign_campaign_id = insert_campaign(db_session, org_b)

    response = client.post(
        "/api/analysis/refresh",
        headers=auth_header(token_a),
        json={"campaign_ids": [str(foreign_campaign_id)]},
    )
    assert response.status_code == 422
    assert str(foreign_campaign_id) in response.json()["detail"]


def test_refresh_rejects_nonexistent_campaign_ids(client: TestClient) -> None:
    token, _ = _register_and_login(
        client,
        name="Owner",
        email="owner2@example.com",
        password="correct-password",
        organization_name="Org",
    )
    fake_campaign_id = uuid4()

    response = client.post(
        "/api/analysis/refresh",
        headers=auth_header(token),
        json={"campaign_ids": [str(fake_campaign_id)]},
    )
    assert response.status_code == 422


def test_refresh_rejects_explicit_empty_campaign_id_list(client: TestClient) -> None:
    token, _ = _register_and_login(
        client,
        name="Owner",
        email="owner3@example.com",
        password="correct-password",
        organization_name="Org",
    )

    response = client.post(
        "/api/analysis/refresh",
        headers=auth_header(token),
        json={"campaign_ids": []},
    )
    assert response.status_code == 422


def test_refresh_is_idempotent_while_a_job_is_pending(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="owner4@example.com",
        password="correct-password",
        organization_name="Org",
    )

    first = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
    second = client.post("/api/analysis/refresh", headers=auth_header(token), json={})

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]

    all_jobs = list(
        db_session.scalars(select(Job).where(Job.organization_id == organization_id)).all()
    )
    assert len(all_jobs) == 1


def test_refresh_does_not_dedupe_across_organizations(client: TestClient) -> None:
    token_a, _ = _register_and_login(
        client,
        name="Org A Owner",
        email="a2@example.com",
        password="password-a",
        organization_name="Org A2",
    )
    token_b, _ = _register_and_login(
        client,
        name="Org B Owner",
        email="b2@example.com",
        password="password-b",
        organization_name="Org B2",
    )

    response_a = client.post("/api/analysis/refresh", headers=auth_header(token_a), json={})
    response_b = client.post("/api/analysis/refresh", headers=auth_header(token_b), json={})

    assert response_a.status_code == 202
    assert response_b.status_code == 202
    assert response_a.json()["job_id"] != response_b.json()["job_id"]


def test_refresh_starts_a_new_job_once_the_previous_one_finished(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="owner5@example.com",
        password="correct-password",
        organization_name="Org",
    )

    first = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
    first_job_id = UUID(first.json()["job_id"])

    job = db_session.get(Job, first_job_id)
    assert job is not None
    job.status = "SUCCESS"
    db_session.commit()

    second = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
    assert second.status_code == 202
    second_job_id = UUID(second.json()["job_id"])
    assert second_job_id != first_job_id

    all_jobs = list(
        db_session.scalars(select(Job).where(Job.organization_id == organization_id)).all()
    )
    assert len(all_jobs) == 2


def test_concurrent_refresh_requests_create_only_one_job(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="owner6@example.com",
        password="correct-password",
        organization_name="Org",
    )

    def _fire() -> int:
        response = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
        return response.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        status_codes = list(pool.map(lambda _: _fire(), range(8)))

    assert all(code == 202 for code in status_codes)

    all_jobs = list(
        db_session.scalars(select(Job).where(Job.organization_id == organization_id)).all()
    )
    assert len(all_jobs) == 1


def test_refresh_response_never_exposes_model_run_id(client: TestClient) -> None:
    token, _ = _register_and_login(
        client,
        name="Owner",
        email="owner7@example.com",
        password="correct-password",
        organization_name="Org",
    )

    response = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
    assert "model_run_id" not in response.json()
