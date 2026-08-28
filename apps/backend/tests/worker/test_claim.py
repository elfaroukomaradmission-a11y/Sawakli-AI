from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from sawakli.db.models.organization import Organization
from sawakli.shared.enums import JobStatus
from sawakli.worker.jobs.claim import claim_next_job


def _create_test_org(
    db: Session,
    name: str,
) -> UUID:
    """Create an organization for a claim integration test."""
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
    priority: str,
    created_at: datetime,
) -> Job:
    """Create a pending job for a claim integration test."""
    job = Job(
        id=uuid4(),
        organization_id=organization_id,
        campaign_ids=None,
        triggered_by_user_id=None,
        status=JobStatus.PENDING.value,
        priority=priority,
        created_at=created_at,
        claimed_at=None,
        retry_count=0,
        max_retries=3,
        next_retry_at=None,
        timeout_seconds=300,
        model_run_id=None,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def _delete_org(
    db: Session,
    organization_id: UUID,
) -> None:
    """Delete an organization's test data."""
    db.execute(delete(Job).where(Job.organization_id == organization_id))
    db.execute(delete(Organization).where(Organization.id == organization_id))
    db.commit()


def test_claim_order_high_before_low_and_oldest_first(
    db_session: Session,
) -> None:
    """
    HIGH jobs are claimed before LOW jobs.

    Within the same priority, older jobs are claimed first.

    Each job belongs to a different organization because the database
    intentionally allows only one inflight job per organization.
    """
    now = datetime.now(UTC)

    organization_ids: list[UUID] = []

    try:
        high_old_org = _create_test_org(db_session, "High Old Org")
        high_new_org = _create_test_org(db_session, "High New Org")
        low_old_org = _create_test_org(db_session, "Low Old Org")
        low_new_org = _create_test_org(db_session, "Low New Org")

        organization_ids.extend(
            [
                high_old_org,
                high_new_org,
                low_old_org,
                low_new_org,
            ]
        )

        high_old = _create_job(
            db_session,
            high_old_org,
            priority="HIGH",
            created_at=now - timedelta(minutes=10),
        )
        high_new = _create_job(
            db_session,
            high_new_org,
            priority="HIGH",
            created_at=now - timedelta(minutes=5),
        )
        low_old = _create_job(
            db_session,
            low_old_org,
            priority="LOW",
            created_at=now - timedelta(minutes=20),
        )
        low_new = _create_job(
            db_session,
            low_new_org,
            priority="LOW",
            created_at=now - timedelta(minutes=2),
        )

        expected_order = [
            high_old.id,
            high_new.id,
            low_old.id,
            low_new.id,
        ]

        claimed_order: list[UUID] = []

        for _ in range(4):
            statement = claim_next_job()

            job = db_session.execute(statement).scalar_one_or_none()

            assert job is not None

            claimed_order.append(job.id)

            # Advance the claimed job out of PENDING so the next claim
            # selects the next eligible job, exactly as the real worker loop does.
            job.status = JobStatus.RUNNING.value
            job.claimed_at = datetime.now(UTC)

            db_session.commit()

        assert claimed_order == expected_order

    finally:
        for organization_id in organization_ids:
            _delete_org(db_session, organization_id)


def test_concurrent_claims_prevent_double_claiming(
    db_session: Session,
) -> None:
    """
    Two workers attempting to claim the same PENDING job concurrently
    cannot both claim it.

    Each worker uses its own database session. The first worker keeps
    the row lock until the second worker attempts the same claim.
    """
    organization_id = _create_test_org(
        db_session,
        "Concurrent Claim Org",
    )

    try:
        job = _create_job(
            db_session,
            organization_id,
            priority="HIGH",
            created_at=datetime.now(UTC),
        )

        from sawakli.db.session import SessionLocal

        barrier = Barrier(2)

        def worker_attempt() -> UUID | None:
            """Attempt to claim the same pending job in a separate session."""
            session = SessionLocal()

            try:
                statement = claim_next_job()
                claimed_job = session.execute(statement).scalar_one_or_none()

                # Both workers reach this point before either transaction
                # commits, so the row lock remains held by the winner.
                barrier.wait()

                if claimed_job is None:
                    session.rollback()
                    return None

                claimed_id = claimed_job.id

                claimed_job.status = JobStatus.RUNNING.value
                claimed_job.claimed_at = datetime.now(UTC)

                session.commit()

                return claimed_id

            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: worker_attempt(),
                    range(2),
                )
            )

        successful_claims = [result for result in results if result == job.id]

        assert len(successful_claims) == 1

        db_session.refresh(job)

        assert job.status == JobStatus.RUNNING.value
        assert job.claimed_at is not None

    finally:
        _delete_org(db_session, organization_id)
