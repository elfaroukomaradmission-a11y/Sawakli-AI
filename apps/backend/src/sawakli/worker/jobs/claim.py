from sqlalchemy import Select, case, select

from sawakli.db.models.jobs import Job


def claim_next_job() -> Select[tuple[Job]]:
    """Build the query for the highest-priority pending job."""
    priority_rank = case(
        (Job.priority == "HIGH", 0),
        (Job.priority == "LOW", 1),
    )

    return (
        select(Job)
        .where(Job.status == "PENDING")
        .order_by(
            priority_rank.asc(),
            Job.created_at.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
