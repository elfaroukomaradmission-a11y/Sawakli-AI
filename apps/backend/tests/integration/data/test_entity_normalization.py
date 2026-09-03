import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from sawakli.data.normalization.pipeline import normalize_and_upsert_batch
from sawakli.data.staging.models import StagedCampaignRow

# The integration tests only run when a real PostgreSQL test database
# is provided through TEST_DATABASE_URL.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set — skipping real Postgres integration tests",
)


@pytest.fixture
def engine():
    # Create an SQLAlchemy engine connected to the test database.
    # This must point to sawakli_test, never the main database.
    return sa.create_engine(TEST_DATABASE_URL)


@pytest.fixture
def seeded_ids(engine):
    # Create unique IDs so this test never conflicts with existing test data.
    org_id = uuid.uuid4()
    data_source_id = uuid.uuid4()

    # Seed the minimum parent records required by the campaigns table.
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
            {"id": org_id, "name": "DATA-04 Test Org"},
        )

        conn.execute(
            sa.text(
                "INSERT INTO data_sources "
                "(id, organization_id, provider, status) "
                "VALUES (:id, :org_id, 'csv_demo', 'demo_data')"
            ),
            {
                "id": data_source_id,
                "org_id": org_id,
            },
        )

    # Return the IDs so the tests can build staged rows.
    yield org_id, data_source_id

    # Remove test data after the test finishes.
    # Campaigns are deleted before their parent data source.
    with engine.begin() as conn:
        conn.execute(
            sa.text("DELETE FROM campaigns WHERE organization_id = :org_id"),
            {"org_id": org_id},
        )

        conn.execute(
            sa.text("DELETE FROM data_sources WHERE id = :id"),
            {"id": data_source_id},
        )

        conn.execute(
            sa.text("DELETE FROM organizations WHERE id = :id"),
            {"id": org_id},
        )


def make_row(org_id, data_source_id, budget=100.0):
    # Build one CSV-style staged campaign row.
    # CSV has no external ID, so DATA-04 must use the
    # data-source + campaign-name + platform fallback identity.
    return StagedCampaignRow(
        organization_id=org_id,
        data_source_id=data_source_id,
        provider="csv_demo",
        external_id=None,
        campaign_name="Summer Campaign",
        platform_raw="meta",
        status_raw=None,
        objective=None,
        budget=budget,
        start_date_raw="2026-08-30",
        end_date_raw=None,
    )


def test_normalization_is_idempotent(engine, seeded_ids) -> None:
    # First run: the campaign should be inserted.
    # Second run: the same campaign should be updated,
    # not inserted again.
    org_id, data_source_id = seeded_ids
    row = make_row(org_id, data_source_id)

    with engine.begin() as connection:
        db = Session(bind=connection)

        first = normalize_and_upsert_batch(db, [row])
        db.flush()

        second = normalize_and_upsert_batch(db, [row])
        db.flush()

        # Both imports must return the exact same campaign ID.
        assert first.results[0].campaign_id == second.results[0].campaign_id

        # Only one campaign must exist after importing the same
        # source row twice.
        count = db.execute(
            sa.text("SELECT COUNT(*) FROM campaigns WHERE organization_id = :org_id"),
            {"org_id": org_id},
        ).scalar_one()

        assert count == 1


def test_normalization_updates_existing_campaign(engine, seeded_ids) -> None:
    # Import the campaign once with one budget.
    # Import it again with a changed budget.
    # The existing row must be updated rather than duplicated.
    org_id, data_source_id = seeded_ids

    with engine.begin() as connection:
        db = Session(bind=connection)

        first = normalize_and_upsert_batch(
            db,
            [make_row(org_id, data_source_id, budget=100.0)],
        )
        db.flush()

        # Same campaign identity, but the budget changed.
        second = normalize_and_upsert_batch(
            db,
            [make_row(org_id, data_source_id, budget=250.0)],
        )
        db.flush()

        # The update must happen on the existing campaign.
        assert first.results[0].campaign_id == second.results[0].campaign_id

        # Verify that the stored value was actually updated.
        budget = db.execute(
            sa.text("SELECT budget FROM campaigns WHERE id = :campaign_id"),
            {"campaign_id": first.results[0].campaign_id},
        ).scalar_one()

        assert float(budget) == 250.0
