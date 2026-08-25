from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from sawakli.db.models.jobs import Job
from sawakli.shared.enums import JobStatus
from sawakli.worker.jobs.claim import claim_next_job
from sawakli.worker.jobs.lifecycle import transition_job_status
from sawakli.worker.orchestration.execute import execute_job


def _save_transition(
    db: Session,
    job: Job,
    proposed_status: JobStatus,
) -> JobStatus:
    current_status = JobStatus(job.status)

    try:
        final_status = transition_job_status(
            current_status,
            proposed_status,
        )
    except ValueError:
        final_status = JobStatus.FAILED

    job.status = final_status.value
    db.flush()

    return final_status


def _get_running_job(db: Session) -> Job | None:
    # Select the oldest RUNNING job for the execution pipeline.
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.RUNNING.value)
        .order_by(Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    return db.execute(stmt).scalar_one_or_none()


def run_once(db: Session) -> list[Job]:
    processed_jobs: list[Job] = []

    # Select a PENDING job for the claim pipeline.
    claim_stmt = claim_next_job()
    pending_job = db.execute(claim_stmt).scalar_one_or_none()

    # Select an already-RUNNING job before changing the PENDING job.
    running_job = _get_running_job(db)

    if pending_job is not None:
        proposed_status = JobStatus.RUNNING

        final_status = _save_transition(
            db,
            pending_job,
            proposed_status,
        )

        if final_status == JobStatus.RUNNING:
            pending_job.claimed_at = datetime.now(UTC)

        processed_jobs.append(pending_job)

    if running_job is not None:
        proposed_status = execute_job(running_job)

        _save_transition(
            db,
            running_job,
            proposed_status,
        )

        processed_jobs.append(running_job)

    db.commit()

    for job in processed_jobs:
        db.refresh(job)

    return processed_jobs
