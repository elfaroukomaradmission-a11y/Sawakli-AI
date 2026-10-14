"""Idempotent demo-login seed for browser/E2E runs (QA-00).

Creates (or repairs) one demo user and links it, as ``owner``, to the Nour Fashion Co.
organization that migration ``0009_seed_demo_data`` inserts with its 90 days of demo data.
The organization itself is never created here: if it is missing, the seed refuses.

Run from ``apps/backend`` against the database in ``DATABASE_URL``::

    SAWAKLI_DEMO_PASSWORD=<choose-a-local-password> python -m tests.fixtures.seed

The password comes only from ``SAWAKLI_DEMO_PASSWORD`` and is never printed. Running the seed
again with the same password changes nothing.
"""

import os
import sys
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sawakli.core.security import hash_password, verify_password
from sawakli.db.models.organization import Organization
from sawakli.db.models.organization_member import OrganizationMember
from sawakli.db.models.user import User

DEMO_ORGANIZATION_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
DEMO_EMAIL = "demo@nourfashion.example"
DEMO_NAME = "Nour Fashion Demo"
DEMO_ROLE = "owner"
PASSWORD_ENV = "SAWAKLI_DEMO_PASSWORD"


class SeedError(Exception):
    """The database is not in a state the demo login can be attached to."""


def seed(db: Session, password: str) -> bool:
    """Ensure the demo login exists and belongs only to Nour Fashion Co. Returns True if changed."""
    if db.get(Organization, DEMO_ORGANIZATION_ID) is None:
        raise SeedError(
            f"organization {DEMO_ORGANIZATION_ID} (Nour Fashion Co.) not found; "
            "run `alembic upgrade head` on a database that includes migration 0009"
        )

    changed = False
    user = db.scalar(select(User).where(func.lower(User.email) == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, hashed_password=hash_password(password), name=DEMO_NAME)
        db.add(user)
        db.flush()
        changed = True
    elif not verify_password(password, user.hashed_password):
        user.hashed_password = hash_password(password)
        changed = True

    # Login uses the user's membership to pick the organization, so the demo user must have
    # exactly one: Nour Fashion Co. Anything else is refused rather than silently deleted.
    others = db.scalars(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id != DEMO_ORGANIZATION_ID,
        )
    ).all()
    if others:
        db.rollback()
        raise SeedError(f"{DEMO_EMAIL} also belongs to other organization(s); fix that manually")

    membership = db.get(OrganizationMember, (user.id, DEMO_ORGANIZATION_ID))
    if membership is None:
        db.add(
            OrganizationMember(
                user_id=user.id, organization_id=DEMO_ORGANIZATION_ID, role=DEMO_ROLE
            )
        )
        changed = True
    elif membership.role != DEMO_ROLE:
        membership.role = DEMO_ROLE
        changed = True

    db.commit()
    return changed


def main() -> int:
    password = os.environ.get(PASSWORD_ENV, "")
    if not password.strip():
        print(
            f"refusing: set {PASSWORD_ENV} to the demo password (it is never printed)",
            file=sys.stderr,
        )
        return 2

    from sawakli.db.session import SessionLocal

    with SessionLocal() as db:
        try:
            changed = seed(db, password)
        except SeedError as exc:
            print(f"refusing: {exc}", file=sys.stderr)
            return 1
    state = "created/updated" if changed else "already up to date"
    print(f"demo login {state}: {DEMO_EMAIL} -> Nour Fashion Co. ({DEMO_ORGANIZATION_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
