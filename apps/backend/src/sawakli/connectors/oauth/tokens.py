"""Connector-owned OAuth token boundary.

store_oauth_token() / refresh_token() / check_connection_status(), per
INT-01 §2.7 and the Connector Layer Report §6.4. Ownership rule (INT-01
§3): this is the only code in the system allowed to read, write, or decrypt
a token value — Backend only ever passes through an OAuth authorization
code, it never sees a token.

These functions take their dependencies (repo, exchanger) as arguments
rather than reaching for a global connection, so none of this needs a live
Postgres connector_tokens table or a real network call to a provider to be
fully unit tested. A Postgres-backed TokenRepository and an HTTP-backed
TokenExchanger get wired in once DATA-01's data_sources table lands.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from ..errors import ConnectorError
from .models import (
    ConnectionStatus,
    ExchangedToken,
    InvalidAuthCodeError,
    Provider,
    ProviderUnreachableError,
    RefreshDeniedError,
    StoredToken,
    TokenErrorKind,
    TokenExchanger,
    TokenRepository,
)


def store_oauth_token(
    data_source_id: UUID,
    provider: Provider,
    auth_code: str,
    *,
    repo: TokenRepository,
    exchanger: TokenExchanger,
) -> bool | ConnectorError:
    """Exchange an auth code for a token and store it.

    Called by Backend right after the OAuth redirect callback succeeds.
    Backend hands over only the authorization code — never a token value.
    Returns True on success, or a typed ConnectorError.
    """
    try:
        exchanged = exchanger.exchange_auth_code(provider, auth_code)
    except InvalidAuthCodeError:
        return ConnectorError(
            kind=TokenErrorKind.INVALID_AUTH_CODE,
            message=(
                f"{provider} rejected the authorization code for data_source_id={data_source_id}."
            ),
            user_message="That connection didn't complete. Please try connecting again.",
            retryable=False,
        )
    except ProviderUnreachableError:
        return ConnectorError(
            kind=TokenErrorKind.PROVIDER_UNREACHABLE,
            message=f"{provider} OAuth endpoint unreachable during code exchange.",
            user_message="We couldn't reach the provider right now. Please try again shortly.",
            retryable=True,
        )

    _save_exchanged_token(data_source_id, provider, exchanged, repo=repo)
    return True


def refresh_token(
    data_source_id: UUID,
    provider: Provider,
    *,
    repo: TokenRepository,
    exchanger: TokenExchanger,
) -> datetime | None | ConnectorError:
    """Swap a near-expiry token for a new one.

    Called by Backend or the Worker on near-expiry. Returns the new expiry
    on success (None if the provider's refresh response didn't include
    one — same as ExchangedToken.expires_at), or a typed ConnectorError.
    """
    existing = repo.get(data_source_id)
    if existing is None:
        return ConnectorError(
            kind=TokenErrorKind.REFRESH_DENIED,
            message=f"No stored token for data_source_id={data_source_id}; nothing to refresh.",
            user_message="This connection needs to be set up again.",
            retryable=False,
        )
    if existing.refresh_token is None:
        # connector_tokens.refresh_token_encrypted is nullable — some
        # providers' grants never issue one. Nothing to refresh with, and
        # re-running the auth-code flow is the only way forward.
        return ConnectorError(
            kind=TokenErrorKind.REFRESH_DENIED,
            message=f"No refresh token stored for data_source_id={data_source_id}.",
            user_message="This connection needs to be set up again.",
            retryable=False,
        )

    try:
        exchanged = exchanger.exchange_refresh_token(provider, existing.refresh_token)
    except RefreshDeniedError:
        return ConnectorError(
            kind=TokenErrorKind.REFRESH_DENIED,
            message=f"{provider} rejected the refresh token for data_source_id={data_source_id}.",
            user_message="This connection has expired. Please reconnect.",
            retryable=False,
        )
    except ProviderUnreachableError:
        return ConnectorError(
            kind=TokenErrorKind.PROVIDER_UNREACHABLE,
            message=f"{provider} OAuth endpoint unreachable during refresh.",
            user_message="We couldn't refresh this connection right now. We'll try again shortly.",
            retryable=True,
        )

    _save_exchanged_token(data_source_id, provider, exchanged, repo=repo)
    return exchanged.expires_at


def check_connection_status(
    data_source_id: UUID,
    *,
    repo: TokenRepository,
    last_synced_at: datetime | None = None,
) -> ConnectionStatus:
    """Report connection health without ever exposing the token itself.

    Never errors (INT-01 §2.7) — a missing or expired token just produces
    connected=False / token_valid=False.

    `last_synced_at` comes from data_sources.last_synced_at (Data
    Layer-owned, but readable by Connector Layer per INT-01's Ownership &
    Access Matrix) and is passed in by the caller — this module has no
    data_sources access of its own, so it doesn't reach for that table
    directly.
    """
    stored = repo.get(data_source_id)
    if stored is None:
        return ConnectionStatus(
            connected=False, token_valid=False, last_successful_call_at=last_synced_at
        )

    # expires_at is nullable in connector_tokens — a provider that issues a
    # non-expiring token has no expiry to check. No known expiry means we
    # have no evidence the token is invalid, so it's treated as valid
    # rather than assumed expired.
    token_valid = stored.expires_at is None or stored.expires_at > datetime.now(UTC)
    return ConnectionStatus(
        connected=True,
        token_valid=token_valid,
        last_successful_call_at=last_synced_at,
    )


def _save_exchanged_token(
    data_source_id: UUID,
    provider: Provider,
    exchanged: ExchangedToken,
    *,
    repo: TokenRepository,
) -> None:
    """Shared save path for both store and refresh."""
    repo.save(
        StoredToken(
            data_source_id=data_source_id,
            provider=provider,
            access_token=exchanged.access_token,
            refresh_token=exchanged.refresh_token,
            expires_at=exchanged.expires_at,
            last_refreshed_at=datetime.now(UTC),
        )
    )
