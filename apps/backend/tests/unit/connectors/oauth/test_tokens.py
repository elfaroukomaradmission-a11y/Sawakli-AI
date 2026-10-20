import base64
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from sawakli.connectors.errors import ConnectorError
from sawakli.connectors.oauth.crypto import decrypt_token, encrypt_token
from sawakli.connectors.oauth.models import (
    ExchangedToken,
    InvalidAuthCodeError,
    Provider,
    ProviderUnreachableError,
    RefreshDeniedError,
    StoredToken,
    TokenErrorKind,
)
from sawakli.connectors.oauth.repository import InMemoryTokenRepository
from sawakli.connectors.oauth.tokens import (
    check_connection_status,
    refresh_token,
    store_oauth_token,
)

KEY = base64.b64decode(base64.b64encode(b"k" * 32))
DATA_SOURCE_ID = uuid.uuid4()
PROVIDER = Provider.GOOGLE_ADS
FUTURE = datetime.now(UTC) + timedelta(hours=1)
PAST = datetime.now(UTC) - timedelta(hours=1)


class FakeExchanger:
    """Test double standing in for a real provider's OAuth token endpoint."""

    def __init__(self, *, auth_code_result=None, refresh_result=None, raises=None):
        self._auth_code_result = auth_code_result
        self._refresh_result = refresh_result
        self._raises = raises

    def exchange_auth_code(self, provider: str, auth_code: str) -> ExchangedToken:
        if self._raises is not None:
            raise self._raises
        assert self._auth_code_result is not None
        return self._auth_code_result

    def exchange_refresh_token(self, provider: str, refresh_token: str) -> ExchangedToken:
        if self._raises is not None:
            raise self._raises
        assert self._refresh_result is not None
        return self._refresh_result


def make_repo() -> InMemoryTokenRepository:
    return InMemoryTokenRepository(KEY)


# --- store_oauth_token() ---


def test_store_success_saves_token_and_returns_true():
    repo = make_repo()
    exchanger = FakeExchanger(
        auth_code_result=ExchangedToken(
            access_token="access-1", refresh_token="refresh-1", expires_at=FUTURE
        )
    )

    result = store_oauth_token(
        DATA_SOURCE_ID, PROVIDER, "auth-code-abc", repo=repo, exchanger=exchanger
    )

    assert result is True
    stored = repo.get(DATA_SOURCE_ID)
    assert stored.access_token == "access-1"
    assert stored.refresh_token == "refresh-1"
    assert stored.provider == PROVIDER


def test_store_invalid_auth_code():
    repo = make_repo()
    exchanger = FakeExchanger(raises=InvalidAuthCodeError())

    result = store_oauth_token(DATA_SOURCE_ID, PROVIDER, "bad-code", repo=repo, exchanger=exchanger)

    assert isinstance(result, ConnectorError)
    assert result.kind == TokenErrorKind.INVALID_AUTH_CODE
    assert result.retryable is False
    assert repo.get(DATA_SOURCE_ID) is None


def test_store_provider_unreachable():
    repo = make_repo()
    exchanger = FakeExchanger(raises=ProviderUnreachableError())

    result = store_oauth_token(
        DATA_SOURCE_ID, PROVIDER, "auth-code-abc", repo=repo, exchanger=exchanger
    )

    assert isinstance(result, ConnectorError)
    assert result.kind == TokenErrorKind.PROVIDER_UNREACHABLE
    assert result.retryable is True
    assert repo.get(DATA_SOURCE_ID) is None


# --- refresh_token() ---


def test_refresh_success_updates_stored_token():
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="old-access",
            refresh_token="old-refresh",
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )
    new_expiry = FUTURE + timedelta(hours=1)
    exchanger = FakeExchanger(
        refresh_result=ExchangedToken(
            access_token="new-access", refresh_token="new-refresh", expires_at=new_expiry
        )
    )

    result = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert result == new_expiry
    stored = repo.get(DATA_SOURCE_ID)
    assert stored.access_token == "new-access"
    assert stored.refresh_token == "new-refresh"
    assert stored.expires_at == new_expiry


def test_refresh_with_no_existing_token_is_refresh_denied():
    repo = make_repo()
    exchanger = FakeExchanger()  # never called

    result = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert isinstance(result, ConnectorError)
    assert result.kind == TokenErrorKind.REFRESH_DENIED
    assert result.retryable is False


def test_refresh_denied_by_provider():
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="old-access",
            refresh_token="revoked-refresh",
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )
    exchanger = FakeExchanger(raises=RefreshDeniedError())

    result = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert isinstance(result, ConnectorError)
    assert result.kind == TokenErrorKind.REFRESH_DENIED
    assert result.retryable is False


def test_refresh_provider_unreachable():
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="old-access",
            refresh_token="old-refresh",
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )
    exchanger = FakeExchanger(raises=ProviderUnreachableError())

    result = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert isinstance(result, ConnectorError)
    assert result.kind == TokenErrorKind.PROVIDER_UNREACHABLE
    assert result.retryable is True


# --- check_connection_status() ---


def test_status_no_token_is_not_connected():
    repo = make_repo()
    status = check_connection_status(DATA_SOURCE_ID, repo=repo)

    assert status.connected is False
    assert status.token_valid is False
    assert status.last_successful_call_at is None


def test_status_valid_token_is_connected():
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="access",
            refresh_token="refresh",
            expires_at=FUTURE,
            last_refreshed_at=PAST,
        )
    )

    status = check_connection_status(DATA_SOURCE_ID, repo=repo)

    assert status.connected is True
    assert status.token_valid is True


def test_status_expired_token_is_connected_but_invalid():
    """An expired token still means a connection exists — it just needs a
    refresh. This must never come back as an error (INT-01 §2.7)."""
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="access",
            refresh_token="refresh",
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )

    status = check_connection_status(DATA_SOURCE_ID, repo=repo)

    assert status.connected is True
    assert status.token_valid is False


def test_status_passes_through_last_synced_at():
    repo = make_repo()
    synced = datetime(2026, 8, 20, tzinfo=UTC)

    status = check_connection_status(DATA_SOURCE_ID, repo=repo, last_synced_at=synced)

    assert status.last_successful_call_at == synced


def test_status_never_raises_for_unknown_data_source():
    """Sanity check on the contract itself: no exception path exists for a
    data_source_id the repository has never seen."""
    repo = make_repo()
    status = check_connection_status(uuid.uuid4(), repo=repo)
    assert status.connected is False


def test_status_null_expiry_is_treated_as_valid():
    """expires_at is nullable — a provider that issues a non-expiring token
    has nothing to compare against. No evidence of expiry means valid, not
    an assumed failure."""
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="access",
            refresh_token="refresh",
            expires_at=None,
            last_refreshed_at=PAST,
        )
    )

    status = check_connection_status(DATA_SOURCE_ID, repo=repo)

    assert status.connected is True
    assert status.token_valid is True


def test_refresh_with_no_stored_refresh_token_is_refresh_denied():
    """refresh_token_encrypted is nullable — some providers never issue one.
    Nothing to refresh with; must fail cleanly, not call the exchanger with None."""
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="access",
            refresh_token=None,
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )
    exchanger = FakeExchanger()  # must never be called

    result = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert isinstance(result, ConnectorError)
    assert result.kind == TokenErrorKind.REFRESH_DENIED


def test_refresh_without_new_refresh_token_keeps_existing_one():
    """A provider's refresh response may omit the refresh token. The stored
    one is still valid and must survive; access token and expiry update."""
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="old-access",
            refresh_token="original-refresh",
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )
    exchanger = FakeExchanger(
        refresh_result=ExchangedToken(
            access_token="new-access", refresh_token=None, expires_at=FUTURE
        )
    )

    result = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert result == FUTURE
    stored = repo.get(DATA_SOURCE_ID)
    assert stored.refresh_token == "original-refresh"
    assert stored.access_token == "new-access"
    assert stored.expires_at == FUTURE


def test_two_refreshes_without_new_refresh_token_both_succeed():
    repo = make_repo()
    repo.save(
        StoredToken(
            data_source_id=DATA_SOURCE_ID,
            provider=PROVIDER,
            access_token="old-access",
            refresh_token="original-refresh",
            expires_at=PAST,
            last_refreshed_at=PAST,
        )
    )
    exchanger = FakeExchanger(
        refresh_result=ExchangedToken(
            access_token="new-access", refresh_token=None, expires_at=FUTURE
        )
    )

    first = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)
    second = refresh_token(DATA_SOURCE_ID, PROVIDER, repo=repo, exchanger=exchanger)

    assert first == FUTURE
    assert second == FUTURE
    assert repo.get(DATA_SOURCE_ID).refresh_token == "original-refresh"


class UndecryptableRepository:
    """Repository whose stored row can't be decrypted, the way a real
    repository behaves after a key change or byte corruption."""

    def __init__(self, blob: bytes, key: bytes) -> None:
        self._blob = blob
        self._key = key

    def get(self, data_source_id):
        decrypt_token(self._blob, self._key)  # raises before a token is built
        raise AssertionError("decryption unexpectedly succeeded")

    def save(self, token):
        raise AssertionError("status check must not write")


OTHER_KEY = base64.b64decode(base64.b64encode(b"o" * 32))


def test_status_wrong_key_is_connected_but_invalid_and_does_not_raise(caplog):
    repo = UndecryptableRepository(encrypt_token("synthetic-access", KEY), OTHER_KEY)

    status = check_connection_status(DATA_SOURCE_ID, repo=repo)

    assert status.connected is True
    assert status.token_valid is False
    # The warning names the source and exception class only, never token material.
    assert str(DATA_SOURCE_ID) in caplog.text
    assert "InvalidTag" in caplog.text
    assert "synthetic-access" not in caplog.text


def test_status_too_short_ciphertext_is_connected_but_invalid():
    repo = UndecryptableRepository(b"short", KEY)

    status = check_connection_status(DATA_SOURCE_ID, repo=repo)

    assert status.connected is True
    assert status.token_valid is False


def test_status_decryption_failure_passes_through_last_synced_at():
    repo = UndecryptableRepository(encrypt_token("synthetic-access", KEY), OTHER_KEY)
    synced = datetime(2026, 10, 20, tzinfo=UTC)

    status = check_connection_status(DATA_SOURCE_ID, repo=repo, last_synced_at=synced)

    assert status.last_successful_call_at == synced


def test_status_database_errors_still_propagate():
    """'Never errors' covers token states, not infrastructure failure."""

    class BrokenRepository:
        def get(self, data_source_id):
            raise RuntimeError("database unavailable")

        def save(self, token):
            raise AssertionError("status check must not write")

    with pytest.raises(RuntimeError):
        check_connection_status(DATA_SOURCE_ID, repo=BrokenRepository())
