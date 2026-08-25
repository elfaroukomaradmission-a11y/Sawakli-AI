import base64
import uuid
from datetime import UTC, datetime

from sawakli.connectors.oauth.models import Provider, StoredToken
from sawakli.connectors.oauth.repository import InMemoryTokenRepository

KEY = base64.b64decode(base64.b64encode(b"k" * 32))
DATA_SOURCE_ID = uuid.uuid4()


def make_token(**overrides) -> StoredToken:
    defaults = dict(
        data_source_id=DATA_SOURCE_ID,
        provider=Provider.GOOGLE_ADS,
        access_token="access-abc",
        refresh_token="refresh-xyz",
        expires_at=datetime(2026, 9, 1, tzinfo=UTC),
        last_refreshed_at=datetime(2026, 8, 24, tzinfo=UTC),
    )
    defaults.update(overrides)
    return StoredToken(**defaults)


def test_get_missing_returns_none():
    repo = InMemoryTokenRepository(KEY)
    assert repo.get(uuid.uuid4()) is None


def test_save_then_get_round_trips():
    repo = InMemoryTokenRepository(KEY)
    token = make_token()

    repo.save(token)
    fetched = repo.get(DATA_SOURCE_ID)

    assert fetched == token


def test_tokens_are_actually_encrypted_at_rest():
    """Guards against a repository that "encrypts" by accident-not-really —
    inspects the internal row directly to confirm plaintext isn't sitting in memory."""
    repo = InMemoryTokenRepository(KEY)
    repo.save(make_token(access_token="plaintext-marker", refresh_token="another-marker"))

    row = repo._rows[DATA_SOURCE_ID]
    assert b"plaintext-marker" not in row.access_token_encrypted
    assert b"another-marker" not in row.refresh_token_encrypted


def test_save_overwrites_existing_row():
    repo = InMemoryTokenRepository(KEY)
    repo.save(make_token(access_token="old-token"))
    repo.save(make_token(access_token="new-token"))

    assert repo.get(DATA_SOURCE_ID).access_token == "new-token"


def test_different_data_sources_are_independent():
    repo = InMemoryTokenRepository(KEY)
    other_id = uuid.uuid4()

    repo.save(make_token(data_source_id=DATA_SOURCE_ID, access_token="token-a"))
    repo.save(make_token(data_source_id=other_id, access_token="token-b"))

    assert repo.get(DATA_SOURCE_ID).access_token == "token-a"
    assert repo.get(other_id).access_token == "token-b"


def test_nullable_refresh_token_round_trips_as_none():
    """connector_tokens.refresh_token_encrypted is nullable — some providers
    never issue one. Must round-trip as None, not crash trying to decrypt it."""
    repo = InMemoryTokenRepository(KEY)
    repo.save(make_token(refresh_token=None))

    fetched = repo.get(DATA_SOURCE_ID)

    assert fetched.refresh_token is None


def test_nullable_expiry_fields_round_trip_as_none():
    """expires_at and last_refreshed_at are also nullable in the real schema."""
    repo = InMemoryTokenRepository(KEY)
    repo.save(make_token(expires_at=None, last_refreshed_at=None))

    fetched = repo.get(DATA_SOURCE_ID)

    assert fetched.expires_at is None
    assert fetched.last_refreshed_at is None
