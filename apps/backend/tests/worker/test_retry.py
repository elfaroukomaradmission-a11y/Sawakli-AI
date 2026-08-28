from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization
from sawakli.shared.enums import JobStatus
from sawakli.worker.jobs.claim import claim_next_job
from sawakli.worker.scheduler.loop import _save_transition


def _create_test_org(db: Session, name: str = "Retry Test Org") -> UUID:
    """Create an organization for retry tests."""
    org_id = uuid4()
    db.add(Organization(id=org_id, name=name))
    db.commit()
    return org_id


def _create_job(
    db: Session,
    organization_id: UUID,
    *,
    status: JobStatus = JobStatus.RUNNING,
    retry_count: int = 0,
    max_retries: int = 3,
    next_retry_at: datetime | None = None,
) -> Job:
    """Create a job with explicit retry state."""
    job = Job(
        id=uuid4(),
        organization_id=organization_id,
        campaign_ids=None,
        triggered_by_user_id=None,
        status=status.value,
        priority="LOW",
        created_at=datetime.now(UTC),
        claimed_at=None,
        retry_count=retry_count,
        max_retries=max_retries,
        next_retry_at=next_retry_at,
        timeout_seconds=300,
        model_run_id=None,
    )
    db.add(job)
    db.commit()
    return job


def _delete_org_data(db: Session, organization_id: UUID) -> None:
    """Remove test jobs and organization."""
    db.execute(delete(Job).where(Job.organization_id == organization_id))
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()


def test_job_fails_twice_then_succeeds(
    db_session: Session,
) -> None:
    """
    A job that fails twice and then succeeds must finish successfully.

    The retry counter must record exactly the two failed attempts.
    """
    org_id = _create_test_org(db_session)
    job = _create_job(db_session, org_id)

    try:
        # First failure:
        # RUNNING -> ERROR -> PENDING
        result = _save_transition(
            db_session,
            job,
            JobStatus.ERROR,
        )

        assert result == JobStatus.PENDING
        assert job.retry_count == 1
        assert job.next_retry_at is not None

        # The job is claimed again after its retry delay.
        job.status = JobStatus.RUNNING.value
        db_session.flush()

        # Second failure:
        # RUNNING -> ERROR -> PENDING
        result = _save_transition(
            db_session,
            job,
            JobStatus.ERROR,
        )

        assert result == JobStatus.PENDING
        assert job.retry_count == 2
        assert job.next_retry_at is not None

        # The job is claimed for its third execution attempt.
        job.status = JobStatus.RUNNING.value
        db_session.flush()

        # Third execution succeeds.
        result = _save_transition(
            db_session,
            job,
            JobStatus.SUCCESS,
        )

        assert result == JobStatus.SUCCESS
        assert job.status == JobStatus.SUCCESS.value

        # Only two retries were needed.
        assert job.retry_count == 2
    finally:
        _delete_org_data(db_session, org_id)


def test_job_stops_after_three_retries(
    db_session: Session,
) -> None:
    """
    A job that fails three times must become FAILED.

    There must not be a fourth retry attempt.
    """
    org_id = _create_test_org(db_session, "Retry Exhaustion Org")
    job = _create_job(db_session, org_id)

    try:
        # First failure -> retry #1.
        result = _save_transition(
            db_session,
            job,
            JobStatus.ERROR,
        )

        assert result == JobStatus.PENDING
        assert job.retry_count == 1

        # Claim the job again.
        job.status = JobStatus.RUNNING.value
        db_session.flush()

        # Second failure -> retry #2.
        result = _save_transition(
            db_session,
            job,
            JobStatus.ERROR,
        )

        assert result == JobStatus.PENDING
        assert job.retry_count == 2

        # Claim the job again.
        job.status = JobStatus.RUNNING.value
        db_session.flush()

        # Third failure exhausts the retry limit.
        result = _save_transition(
            db_session,
            job,
            JobStatus.ERROR,
        )

        assert result == JobStatus.FAILED
        assert job.status == JobStatus.FAILED.value
        assert job.retry_count == 3

        # A FAILED job must not receive another retry.
        assert job.next_retry_at is not None
    finally:
        _delete_org_data(db_session, org_id)


def test_retried_job_waits_until_next_retry_time(
    db_session: Session,
    monkeypatch,
) -> None:
    """
    A retried job cannot be claimed before next_retry_at.

    The clock is fixed/mocked so this test never sleeps.
    """
    from sawakli.worker.jobs import claim as claim_module

    fixed_now = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)

    class FixedDateTime(datetime):
        """Datetime class whose now() method returns the fixed test time."""

        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(claim_module, "datetime", FixedDateTime)

    org_id = _create_test_org(db_session, "Backoff Timing Org")

    try:
        # The retry is scheduled five seconds in the future.
        job = _create_job(
            db_session,
            org_id,
            status=JobStatus.PENDING,
            retry_count=1,
            next_retry_at=fixed_now + timedelta(seconds=5),
        )

        # Before next_retry_at, the job must not be claimable.
        statement = claim_next_job().where(Job.id == job.id)
        claimed_job = db_session.execute(statement).scalar_one_or_none()
        assert claimed_job is None

        # Move the retry time into the past without sleeping.
        job.next_retry_at = fixed_now - timedelta(seconds=1)
        db_session.commit()

        # The same job is now eligible for claiming.
        statement = claim_next_job().where(Job.id == job.id)
        claimed_job = db_session.execute(statement).scalar_one_or_none()

        assert claimed_job is not None
        assert claimed_job.id == job.id
    finally:
        _delete_org_data(db_session, org_id)


def test_concurrent_claims_do_not_double_claim_retried_job(
    db_session: Session,
) -> None:
    """
    Multiple workers must not claim the same retry-ready job simultaneously.

    Each worker uses its own database session, matching real worker behavior.
    """
    from sawakli.db.session import SessionLocal

    org_id = _create_test_org(db_session, "Retry Concurrency Org")

    try:
        job = _create_job(
            db_session,
            org_id,
            status=JobStatus.PENDING,
            retry_count=1,
            next_retry_at=datetime.now(UTC) - timedelta(seconds=1),
        )

        def claim_from_worker() -> UUID | None:
            """Attempt to claim one job using an independent DB session."""
            worker_db = SessionLocal()

            try:
                statement = claim_next_job()
                claimed = worker_db.execute(statement).scalar_one_or_none()

                if claimed is None:
                    return None

                claimed_id = claimed.id

                # Simulate the worker changing the claimed job to RUNNING.
                claimed.status = JobStatus.RUNNING.value
                worker_db.commit()

                return claimed_id
            finally:
                worker_db.close()

        # Several workers attempt to claim simultaneously.
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(
                executor.map(
                    lambda _: claim_from_worker(),
                    range(4),
                )
            )

        successful_claims = [result for result in results if result is not None]

        # Exactly one worker may claim this job.
        assert successful_claims == [job.id]
    finally:
        _delete_org_data(db_session, org_id)
