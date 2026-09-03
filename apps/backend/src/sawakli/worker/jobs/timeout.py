from datetime import datetime

from sawakli.db.models.jobs import Job


def is_job_timed_out(
    job: Job,
    now: datetime,
) -> bool:
    """Return whether a running job has exceeded its timeout."""
    if job.claimed_at is None:
        return False

    timeout_at = job.claimed_at.timestamp() + job.timeout_seconds
    return now.timestamp() >= timeout_at
