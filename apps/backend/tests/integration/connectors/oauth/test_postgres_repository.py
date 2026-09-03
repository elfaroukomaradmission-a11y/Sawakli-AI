"""Integration tests for PostgresTokenRepository against a real database.

Requires a live Postgres reachable via the TEST_DATABASE_URL env var, with
migrations already applied (`alembic upgrade head`). Skipped automatically
if that variable isn't set — the rest of the suite (unit/) never depends on
a real database and stays green without one.

These tests seed their own organizations/data_sources rows first (via raw
SQL, not through this package — Connector Layer never writes those tables)
so connector_tokens' FK to data_sources.id has something real to point at,
the same way it would in production.
"""

from __future__ import annotations

import base64
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa

from sawakli.connectors.oauth.models import Provider, StoredToken
from sawakli.connectors.oauth.repository import PostgresTokenRepository

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set — skipping tests against a real Postgres instance",
)

KEY = base64.b64decode(base64.b64encode(b"k" * 32))


@pytest.fixture
def engine():
    return sa.create_engine(TEST_DATABASE_URL)


@pytest.fixture
def data_source_id(engine):
    """Seed a real organizations + data_sources row via raw SQL (standing in
    for what Backend does on connector setup) so connector_tokens' FK has a
    real target, then clean up afterward."""
    org_id = uuid.uuid4()
    ds_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            sa.text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
            {"id": org_id, "name": "Test Org"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO data_sources (id, organization_id, provider, status) "
                "VALUES (:id, :org_id, 'googleads', 'connected')"
            ),
            {"id": ds_id, "org_id": org_id},
        )
    yield ds_id
    with engine.begin() as conn:
        conn.execute(
            sa.text("DELETE FROM connector_tokens WHERE data_source_id = :id"), {"id": ds_id}
        )
        conn.execute(sa.text("DELETE FROM data_sources WHERE id = :id"), {"id": ds_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


def make_token(data_source_id, **overrides) -> StoredToken:
    defaults = dict(
        data_source_id=data_source_id,
        provider=Provider.GOOGLE_ADS,
        access_token="access-abc",
        refresh_token="refresh-xyz",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        last_refreshed_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return StoredToken(**defaults)


def test_get_missing_returns_none(engine, data_source_id):
    with engine.connect() as conn:
        repo = PostgresTokenRepository(conn, KEY)
        assert repo.get(data_source_id) is None


def test_save_then_get_round_trips_through_real_db(engine, data_source_id):
    token = make_token(data_source_id)
    with engine.begin() as conn:
        repo = PostgresTokenRepository(conn, KEY)
        repo.save(token)

    # fresh connection, proving it actually persisted rather than living in
    # some connection-local cache
    with engine.connect() as conn:
        repo = PostgresTokenRepository(conn, KEY)
        fetched = repo.get(data_source_id)

    assert fetched == token


def test_tokens_are_encrypted_at_rest_in_the_real_table(engine, data_source_id):
    token = make_token(data_source_id, access_token="plaintext-marker")
    with engine.begin() as conn:
        PostgresTokenRepository(conn, KEY).save(token)

    with engine.connect() as conn:
        raw = conn.execute(
            sa.text(
                "SELECT access_token_encrypted FROM connector_tokens WHERE data_source_id = :id"
            ),
            {"id": data_source_id},
        ).scalar_one()

    assert b"plaintext-marker" not in bytes(raw)


def test_save_upserts_on_data_source_id(engine, data_source_id):
    """connector_tokens has UNIQUE(data_source_id) — a second save() for the
    same data_source_id must update the existing row, not violate the
    constraint or create a duplicate."""
    with engine.begin() as conn:
        repo = PostgresTokenRepository(conn, KEY)
        repo.save(make_token(data_source_id, access_token="old-token"))
        repo.save(make_token(data_source_id, access_token="new-token"))

    with engine.connect() as conn:
        row_count = conn.execute(
            sa.text("SELECT COUNT(*) FROM connector_tokens WHERE data_source_id = :id"),
            {"id": data_source_id},
        ).scalar_one()
        fetched = PostgresTokenRepository(conn, KEY).get(data_source_id)

    assert row_count == 1
    assert fetched.access_token == "new-token"


def test_nullable_refresh_token_round_trips_through_real_db(engine, data_source_id):
    token = make_token(data_source_id, refresh_token=None)
    with engine.begin() as conn:
        PostgresTokenRepository(conn, KEY).save(token)

    with engine.connect() as conn:
        fetched = PostgresTokenRepository(conn, KEY).get(data_source_id)

    assert fetched.refresh_token is None


def test_nullable_expiry_fields_round_trip_through_real_db(engine, data_source_id):
    token = make_token(data_source_id, expires_at=None, last_refreshed_at=None)
    with engine.begin() as conn:
        PostgresTokenRepository(conn, KEY).save(token)

    with engine.connect() as conn:
        fetched = PostgresTokenRepository(conn, KEY).get(data_source_id)

    assert fetched.expires_at is None
    assert fetched.last_refreshed_at is None


def test_deleting_data_source_cascades_to_connector_tokens(engine, data_source_id):
    """FK is ON DELETE CASCADE — removing a data_sources row must clean up
    its token automatically, never leave an orphaned encrypted credential
    behind."""
    with engine.begin() as conn:
        PostgresTokenRepository(conn, KEY).save(make_token(data_source_id))

    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM data_sources WHERE id = :id"), {"id": data_source_id})

    with engine.connect() as conn:
        remaining = conn.execute(
            sa.text("SELECT COUNT(*) FROM connector_tokens WHERE data_source_id = :id"),
            {"id": data_source_id},
        ).scalar_one()

    assert remaining == 0
