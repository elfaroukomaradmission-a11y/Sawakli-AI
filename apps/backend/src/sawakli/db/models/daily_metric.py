import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from sawakli.db.session import Base


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    campaign_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("campaigns.id"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    spend: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False)