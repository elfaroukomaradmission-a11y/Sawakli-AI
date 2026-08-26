from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, apply_org_scope, get_auth_context
from sawakli.db.models.jobs import Job
from sawakli.db.session import get_db

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
