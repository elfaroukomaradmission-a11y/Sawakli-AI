from sawakli.shared.enums import JobStatus


def transition_job_status(
    current: JobStatus,
    target: JobStatus,
) -> JobStatus:
    """Validate and return a legal job lifecycle transition."""

    allowed_transitions = {
        JobStatus.PENDING: {
            JobStatus.RUNNING,
            JobStatus.CANCELLED,
        },
        JobStatus.RUNNING: {
            JobStatus.SUCCESS,
            JobStatus.FAILED,
            JobStatus.PARTIAL_SUCCESS,
            JobStatus.CANCELLED,
        },
        JobStatus.SUCCESS: set(),
        JobStatus.FAILED: set(),
        JobStatus.PARTIAL_SUCCESS: set(),
        JobStatus.CANCELLED: set(),
    }

    if target not in allowed_transitions[current]:
        raise ValueError(f"Invalid job status transition: {current} -> {target}")

    return target
