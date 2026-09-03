from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sawakli.db.models.jobs import Job
from sawakli.shared.enums import JobStatus
from sawakli.worker.jobs.timeout import is_job_timed_out


def _create_job(
    *,
    claimed_at: datetime | None,
    timeout_seconds: int = 300,
) -> Job:
    """Create an in-memory job for timeout testing."""
    return Job(
        id=uuid4(),
        organization_id=uuid4(),
        status=JobStatus.RUNNING.value,
        priority="LOW",
        created_at=datetime.now(UTC),
        claimed_at=claimed_at,
        timeout_seconds=timeout_seconds,
    )


def test_running_job_is_timed_out_after_timeout() -> None:
    """A job is timed out once its timeout period has elapsed."""
    claimed_at = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)
    now = claimed_at + timedelta(seconds=300)

    job = _create_job(claimed_at=claimed_at)

    assert is_job_timed_out(job, now) is True


def test_running_job_is_not_timed_out_before_timeout() -> None:
    """A job is not timed out while it is still within its timeout window."""
    claimed_at = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)
    now = claimed_at + timedelta(seconds=299)

    job = _create_job(claimed_at=claimed_at)

    assert is_job_timed_out(job, now) is False


def test_job_without_claimed_at_is_not_timed_out() -> None:
    """A job without a claim timestamp cannot be considered timed out."""
    now = datetime(2026, 8, 28, 10, 5, 0, tzinfo=UTC)

    job = _create_job(claimed_at=None)

    assert is_job_timed_out(job, now) is False


def test_timeout_uses_job_specific_timeout() -> None:
    """The timeout check uses the timeout configured on the individual job."""
    claimed_at = datetime(2026, 8, 28, 10, 0, 0, tzinfo=UTC)
    now = claimed_at + timedelta(seconds=600)

    job = _create_job(
        claimed_at=claimed_at,
        timeout_seconds=600,
    )

    assert is_job_timed_out(job, now) is True
