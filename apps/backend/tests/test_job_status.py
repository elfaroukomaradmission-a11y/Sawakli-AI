from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
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


def test_status_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{uuid4()}/status")
    assert response.status_code == 401


def test_status_returns_pending_for_a_freshly_queued_job(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="status-owner@example.com",
        password="correct-password",
        organization_name="Org",
    )
    job_id = insert_job(db_session, organization_id)

    response = client.get(f"/api/jobs/{job_id}/status", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job_id)
    assert body["status"] == "PENDING"
    assert "created_at" in body


def test_status_reflects_live_state_not_a_cached_value(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="status-owner2@example.com",
        password="correct-password",
        organization_name="Org",
    )
    job_id = insert_job(db_session, organization_id)

    job = db_session.get(Job, job_id)
    assert job is not None
    job.status = "RUNNING"
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}/status", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"

    job.status = "SUCCESS"
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}/status", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"


def test_status_returns_404_for_unknown_job(client: TestClient) -> None:
    token, _ = _register_and_login(
        client,
        name="Owner",
        email="status-owner3@example.com",
        password="correct-password",
        organization_name="Org",
    )

    response = client.get(f"/api/jobs/{uuid4()}/status", headers=auth_header(token))
    assert response.status_code == 404


def test_status_returns_404_not_403_for_another_organizations_job(
    client: TestClient, db_session: Session
) -> None:
    token_a, _ = _register_and_login(
        client,
        name="Org A Owner",
        email="status-a@example.com",
        password="password-a",
        organization_name="Org A",
    )
    _, org_b = _register_and_login(
        client,
        name="Org B Owner",
        email="status-b@example.com",
        password="password-b",
        organization_name="Org B",
    )
    job_b = insert_job(db_session, org_b)

    response = client.get(f"/api/jobs/{job_b}/status", headers=auth_header(token_a))
    assert response.status_code == 404


def test_status_response_includes_campaign_ids_when_present(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="status-owner4@example.com",
        password="correct-password",
        organization_name="Org",
    )
    job_id = insert_job(db_session, organization_id)
    job = db_session.get(Job, job_id)
    assert job is not None
    job.campaign_ids = [str(uuid4())]
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}/status", headers=auth_header(token))
    body = response.json()
    assert body["campaign_ids"] == job.campaign_ids


def test_status_response_never_exposes_model_run_id(
    client: TestClient, db_session: Session
) -> None:
    token, organization_id = _register_and_login(
        client,
        name="Owner",
        email="status-owner5@example.com",
        password="correct-password",
        organization_name="Org",
    )
    job_id = insert_job(db_session, organization_id)
    job = db_session.get(Job, job_id)
    assert job is not None
    job.model_run_id = uuid4()
    db_session.commit()

    response = client.get(f"/api/jobs/{job_id}/status", headers=auth_header(token))
    assert "model_run_id" not in response.json()


def test_end_to_end_refresh_then_poll_status(client: TestClient) -> None:
    token, _ = _register_and_login(
        client,
        name="Owner",
        email="status-owner6@example.com",
        password="correct-password",
        organization_name="Org",
    )

    refresh_response = client.post("/api/analysis/refresh", headers=auth_header(token), json={})
    job_id = refresh_response.json()["job_id"]

    status_response = client.get(f"/api/jobs/{job_id}/status", headers=auth_header(token))
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"
