from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from sawakli.db.models.campaign import CampaignStatus, Platform


class CampaignPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    platform: Platform
    status: CampaignStatus | None
    objective: str | None
    budget: float | None
    start_date: date | None
    end_date: date | None
