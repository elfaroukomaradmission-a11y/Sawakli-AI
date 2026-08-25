import random

from sawakli.db.models.jobs import Job
from sawakli.shared.enums import JobStatus
from sawakli.worker.jobs.lifecycle import transition_job_status


def _simulate_execution_outcome(current: JobStatus) -> JobStatus:
    """Randomly propose a legal or illegal execution outcome for testing.

    lifecycle.py remains the single source of truth for determining
    whether a proposed transition is legal.
    """
    all_statuses = list(JobStatus)
    legal: list[JobStatus] = []
    illegal: list[JobStatus] = []

    for candidate in all_statuses:
        try:
            transition_job_status(current, candidate)
            legal.append(candidate)
        except ValueError:
            illegal.append(candidate)

    return random.choice(legal + illegal)


def execute_job(job: Job) -> JobStatus:
    """Execute a job placeholder and return its proposed outcome."""
    return _simulate_execution_outcome(JobStatus(job.status))