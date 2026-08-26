from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sawakli.db.session import Base

if TYPE_CHECKING:
    from sawakli.db.models.organization import Organization
    from sawakli.db.models.user import User


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)

    user: Mapped["User"] = relationship(back_populates="organization_members")
    organization: Mapped["Organization"] = relationship(back_populates="organization_members")
