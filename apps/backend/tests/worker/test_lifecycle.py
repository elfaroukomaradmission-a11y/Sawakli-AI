import pytest

from sawakli.shared.enums import JobStatus
from sawakli.worker.jobs.lifecycle import transition_job_status


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.PENDING, JobStatus.RUNNING),
        (JobStatus.PENDING, JobStatus.CANCELLED),
        (JobStatus.RUNNING, JobStatus.SUCCESS),
        (JobStatus.RUNNING, JobStatus.FAILED),
        (JobStatus.RUNNING, JobStatus.PARTIAL_SUCCESS),
        (JobStatus.RUNNING, JobStatus.CANCELLED),
        (JobStatus.RUNNING, JobStatus.ERROR),
        (JobStatus.ERROR, JobStatus.PENDING),
        (JobStatus.ERROR, JobStatus.FAILED),
        (JobStatus.ERROR, JobStatus.CANCELLED),
    ],
)
def test_valid_job_status_transitions(current, target):
    assert transition_job_status(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.PENDING, JobStatus.SUCCESS),
        (JobStatus.PENDING, JobStatus.FAILED),
        (JobStatus.PENDING, JobStatus.PARTIAL_SUCCESS),
        (JobStatus.RUNNING, JobStatus.PENDING),
        (JobStatus.SUCCESS, JobStatus.PENDING),
        (JobStatus.SUCCESS, JobStatus.RUNNING),
        (JobStatus.SUCCESS, JobStatus.FAILED),
        (JobStatus.SUCCESS, JobStatus.PARTIAL_SUCCESS),
        (JobStatus.SUCCESS, JobStatus.CANCELLED),
        (JobStatus.SUCCESS, JobStatus.ERROR),
        (JobStatus.FAILED, JobStatus.PENDING),
        (JobStatus.FAILED, JobStatus.RUNNING),
        (JobStatus.FAILED, JobStatus.SUCCESS),
        (JobStatus.FAILED, JobStatus.PARTIAL_SUCCESS),
        (JobStatus.FAILED, JobStatus.CANCELLED),
        (JobStatus.FAILED, JobStatus.ERROR),
        (JobStatus.PARTIAL_SUCCESS, JobStatus.PENDING),
        (JobStatus.PARTIAL_SUCCESS, JobStatus.RUNNING),
        (JobStatus.PARTIAL_SUCCESS, JobStatus.SUCCESS),
        (JobStatus.PARTIAL_SUCCESS, JobStatus.FAILED),
        (JobStatus.PARTIAL_SUCCESS, JobStatus.CANCELLED),
        (JobStatus.PARTIAL_SUCCESS, JobStatus.ERROR),
        (JobStatus.CANCELLED, JobStatus.PENDING),
        (JobStatus.CANCELLED, JobStatus.RUNNING),
        (JobStatus.CANCELLED, JobStatus.SUCCESS),
        (JobStatus.CANCELLED, JobStatus.FAILED),
        (JobStatus.CANCELLED, JobStatus.PARTIAL_SUCCESS),
        (JobStatus.CANCELLED, JobStatus.ERROR),
    ],
)
def test_invalid_job_status_transitions(current, target):
    with pytest.raises(ValueError):
        transition_job_status(current, target)
