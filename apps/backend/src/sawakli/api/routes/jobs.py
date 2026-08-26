from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, apply_org_scope, get_auth_context
from sawakli.api.schemas.jobs import JobStatusResponse
from sawakli.db.models.jobs import Job
from sawakli.db.session import get_db
from sawakli.shared.enums import JobStatus

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


class JobPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID


@router.get("", response_model=list[JobPublic])
def list_jobs(
    auth: CurrentAuth,
    db: DbSession,
    organization_id: Annotated[UUID | None, Query()] = None,
) -> list[JobPublic]:
    """List jobs for the authenticated organization only."""
    _ = organization_id
    statement = apply_org_scope(select(Job), Job, auth.organization.id)
    jobs = list(db.scalars(statement).all())
    return [JobPublic.model_validate(job) for job in jobs]


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    auth: CurrentAuth,
    db: DbSession,
) -> JobStatusResponse:
    """Return the current state of a job ticket.

    A job that exists but belongs to another organization returns 404, the
    same as a job_id that doesn't exist at all -- confirming existence
    across orgs is its own information leak, so the two cases are
    indistinguishable from the outside.
    """
    statement = apply_org_scope(
        select(Job).where(Job.id == job_id),
        Job,
        auth.organization.id,
    )
    job = db.scalar(statement)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        campaign_ids=job.campaign_ids,
        created_at=job.created_at,
    )
