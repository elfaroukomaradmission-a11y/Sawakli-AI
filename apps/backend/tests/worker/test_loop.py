from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization
from sawakli.shared.enums import JobStatus
from sawakli.worker.scheduler.loop import run_once


def _create_test_org(
    db: Session,
    name: str = "Loop Integration Org",
) -> UUID:
    """Create an organization used by an integration test."""
    organization_id = uuid4()

    db.add(
        Organization(
            id=organization_id,
            name=name,
        )
    )
    db.commit()

    return organization_id


def _create_job(
    db: Session,
    organization_id: UUID,
    *,
    status: JobStatus,
    created_at: datetime | None = None,
    claimed_at: datetime | None = None,
    retry_count: int = 0,
    max_retries: int = 3,
    next_retry_at: datetime | None = None,
    timeout_seconds: int = 300,
) -> Job:
    """Create a job with the exact state required by an integration scenario."""
    job = Job(
        id=uuid4(),
        organization_id=organization_id,
        campaign_ids=None,
        triggered_by_user_id=None,
        status=status.value,
        priority="LOW",
        created_at=created_at or datetime.now(UTC),
        claimed_at=claimed_at,
        retry_count=retry_count,
        max_retries=max_retries,
        next_retry_at=next_retry_at,
        timeout_seconds=timeout_seconds,
        model_run_id=None,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def _delete_org_data(
    db: Session,
    organization_id: UUID,
) -> None:
    """Remove test jobs and their organization."""
    db.execute(delete(Job).where(Job.organization_id == organization_id))
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()


def test_run_once_claims_pending_job(
    db_session: Session,
) -> None:
    """run_once claims an eligible PENDING job and moves it to RUNNING."""
    organization_id = _create_test_org(db_session)

    try:
        job = _create_job(
            db_session,
            organization_id,
            status=JobStatus.PENDING,
        )

        processed = run_once(db_session)

        assert any(processed_job.id == job.id for processed_job in processed)

        db_session.refresh(job)

        assert job.status == JobStatus.RUNNING.value
        assert job.claimed_at is not None
    finally:
        _delete_org_data(db_session, organization_id)


def test_run_once_retries_timed_out_running_job(
    db_session: Session,
) -> None:
    """
    A timed-out RUNNING job enters the existing retry flow.

    This verifies the integration:
        timeout detection → loop.py → retry/backoff logic.
    """
    organization_id = _create_test_org(db_session)

    try:
        job = _create_job(
            db_session,
            organization_id,
            status=JobStatus.RUNNING,
            created_at=datetime.now(UTC) - timedelta(minutes=10),
            claimed_at=datetime.now(UTC) - timedelta(minutes=10),
            retry_count=0,
            timeout_seconds=300,
        )

        processed = run_once(db_session)

        assert any(processed_job.id == job.id for processed_job in processed)

        db_session.refresh(job)

        assert job.status == JobStatus.PENDING.value
        assert job.retry_count == 1
        assert job.next_retry_at is not None
    finally:
        _delete_org_data(db_session, organization_id)


def test_run_once_leaves_non_timed_out_running_job_for_execution(
    db_session: Session,
) -> None:
    """
    A RUNNING job still inside its timeout window follows normal execution.

    The test controls execute_job() so the execution result is deterministic.
    """
    organization_id = _create_test_org(db_session)

    try:
        job = _create_job(
            db_session,
            organization_id,
            status=JobStatus.RUNNING,
            claimed_at=datetime.now(UTC) - timedelta(seconds=30),
            timeout_seconds=300,
        )

        from sawakli.worker.scheduler import loop as loop_module

        original_execute_job = loop_module.execute_job

        try:
            loop_module.execute_job = lambda _: JobStatus.SUCCESS

            run_once(db_session)
        finally:
            loop_module.execute_job = original_execute_job

        db_session.refresh(job)

        assert job.status == JobStatus.SUCCESS.value
        assert job.retry_count == 0
    finally:
        _delete_org_data(db_session, organization_id)


def test_timed_out_job_has_priority_over_normal_running_job(
    db_session: Session,
) -> None:
    """
    A timed-out RUNNING job is recovered before a normal RUNNING job.

    Each job belongs to a different organization because the database
    intentionally allows only one inflight job per organization.

    The worker is global, so it can still encounter RUNNING jobs from
    multiple organizations in the same cycle.
    """
    normal_org_id = _create_test_org(
        db_session,
        "Normal Running Org",
    )
    timeout_org_id = _create_test_org(
        db_session,
        "Timed Out Org",
    )

    try:
        older_normal_job = _create_job(
            db_session,
            normal_org_id,
            status=JobStatus.RUNNING,
            created_at=datetime.now(UTC) - timedelta(minutes=10),
            claimed_at=datetime.now(UTC) - timedelta(seconds=30),
            timeout_seconds=300,
        )

        newer_timed_out_job = _create_job(
            db_session,
            timeout_org_id,
            status=JobStatus.RUNNING,
            created_at=datetime.now(UTC) - timedelta(minutes=5),
            claimed_at=datetime.now(UTC) - timedelta(minutes=10),
            timeout_seconds=300,
        )

        from sawakli.worker.scheduler import loop as loop_module

        original_execute_job = loop_module.execute_job

        try:
            loop_module.execute_job = lambda _: JobStatus.SUCCESS

            run_once(db_session)
        finally:
            loop_module.execute_job = original_execute_job

        db_session.refresh(older_normal_job)
        db_session.refresh(newer_timed_out_job)

        assert older_normal_job.status == JobStatus.RUNNING.value
        assert newer_timed_out_job.status == JobStatus.PENDING.value
        assert newer_timed_out_job.retry_count == 1
    finally:
        _delete_org_data(db_session, normal_org_id)
        _delete_org_data(db_session, timeout_org_id)


def test_cancelled_running_job_is_not_overwritten(
    db_session: Session,
) -> None:
    """
    A cancellation occurring while execution is in progress is preserved.

    The test changes the job to CANCELLED during execution, then verifies
    that the worker does not overwrite the cancellation with SUCCESS.
    """
    organization_id = _create_test_org(
        db_session,
        "Cancellation Test Org",
    )

    try:
        job = _create_job(
            db_session,
            organization_id,
            status=JobStatus.RUNNING,
        )

        from sawakli.worker.scheduler import loop as loop_module

        original_execute_job = loop_module.execute_job

        def execute_and_cancel(current_job: Job) -> JobStatus:
            """Simulate cancellation during execution."""
            current_job.status = JobStatus.CANCELLED.value
            db_session.flush()

            return JobStatus.SUCCESS

        try:
            loop_module.execute_job = execute_and_cancel

            run_once(db_session)
        finally:
            loop_module.execute_job = original_execute_job

        db_session.refresh(job)

        assert job.status == JobStatus.CANCELLED.value

    finally:
        _delete_org_data(db_session, organization_id)


def test_concurrent_workers_do_not_double_claim_pending_job(
    db_session: Session,
) -> None:
    """
    Multiple workers attempting to process the same PENDING job
    must not both claim it.
    """
    organization_id = _create_test_org(db_session)

    try:
        job = _create_job(
            db_session,
            organization_id,
            status=JobStatus.PENDING,
        )

        from sawakli.db.session import SessionLocal

        def worker_attempt() -> list[Job]:
            """Run one worker cycle using its own database session."""
            session = SessionLocal()

            try:
                return run_once(session)
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: worker_attempt(),
                    range(2),
                )
            )

        processed_count = sum(
            1 for result in results if any(processed_job.id == job.id for processed_job in result)
        )

        assert processed_count <= 1
    finally:
        _delete_org_data(db_session, organization_id)


def test_concurrent_workers_do_not_recover_same_timed_out_job_twice(
    db_session: Session,
) -> None:
    """
    Multiple workers attempting timeout recovery must not recover
    the same RUNNING job twice.
    """
    organization_id = _create_test_org(db_session)

    try:
        job = _create_job(
            db_session,
            organization_id,
            status=JobStatus.RUNNING,
            claimed_at=datetime.now(UTC) - timedelta(minutes=10),
            retry_count=0,
            timeout_seconds=300,
        )

        from sawakli.db.session import SessionLocal

        def worker_attempt() -> list[Job]:
            """Run one worker cycle using its own database session."""
            session = SessionLocal()

            try:
                return run_once(session)
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: worker_attempt(),
                    range(2),
                )
            )

        processed_count = sum(
            1 for result in results if any(processed_job.id == job.id for processed_job in result)
        )

        db_session.refresh(job)

        assert processed_count <= 1
        assert job.retry_count == 1
    finally:
        _delete_org_data(db_session, organization_id)
