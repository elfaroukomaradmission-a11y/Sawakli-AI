"""Read-only reference to the `campaigns` table for ownership checks.

The Campaign Data API (API-02) hasn't been built yet, so there's no mapped
ORM model for campaigns. This module intentionally does not add one — it
exposes exactly one query (existence + org ownership), nothing else. Any
future full Campaign model belongs to API-02, not here.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import column, select, table
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

_campaigns = table(
    "campaigns",
    column("id", PGUUID(as_uuid=True)),
    column("organization_id", PGUUID(as_uuid=True)),
)


def find_missing_campaign_ids(
    db: Session,
    organization_id: UUID,
    campaign_ids: Sequence[UUID],
) -> set[UUID]:
    """Return the subset of campaign_ids that don't belong to organization_id.

    A campaign_id that doesn't exist at all is also "missing" here — the
    caller doesn't need to distinguish "not found" from "found but not
    yours" for this check.
    """
    if not campaign_ids:
        return set()

    found_ids = set(
        db.scalars(
            select(_campaigns.c.id).where(
                _campaigns.c.organization_id == organization_id,
                _campaigns.c.id.in_(campaign_ids),
            )
        ).all()
    )
    return set(campaign_ids) - found_ids
