from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.session import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    campaign_ids: Mapped[list[object] | None] = mapped_column(
        JSONB,
    )
    triggered_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "PENDING",
            "RUNNING",
            "SUCCESS",
            "FAILED",
            "CANCELLED",
            "PARTIAL_SUCCESS",
            name="job_status_enum",
            create_type=False,
        ),
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        Enum(
            "HIGH",
            "LOW",
            name="job_priority_enum",
            create_type=False,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    model_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        unique=True,
    )
