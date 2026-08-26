from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from sawakli.shared.enums import JobStatus


class AnalysisRefreshRequest(BaseModel):
    # Omitted or null -> all of the org's campaigns. An explicit empty list
    # is rejected below rather than silently treated as "all" or "none" --
    # either reading would be a guess.
    campaign_ids: list[UUID] | None = None

    @field_validator("campaign_ids")
    @classmethod
    def reject_explicit_empty_list(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(value) == 0:
            raise ValueError("campaign_ids must be omitted or non-empty, not an empty list")
        return value


class AnalysisRefreshResponse(BaseModel):
    job_id: UUID
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    campaign_ids: list[UUID] | None = None
    created_at: datetime
