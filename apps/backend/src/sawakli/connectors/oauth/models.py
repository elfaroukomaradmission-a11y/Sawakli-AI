"""Data contracts for the OAuth token boundary.

Mirrors the connector_tokens schema (INT-01 §1.4) closely enough that a
real repository implementation is a thin pass-through, but stays a plain
dataclass so tokens.py's logic never needs a live database to be tested.

Keyed by data_source_id, not org_id + provider. INT-01 §2.7 lists
store_oauth_token(org_id, provider, auth_code) etc., but that predates (or
just never got updated for) Conflict #13's resolution: connector_tokens is
keyed by data_source_id specifically because one org can connect more than
one account on the same provider — org_id + provider can't tell those
apart, data_source_id already can (Backend creates one data_sources row per
connected account). This module uses data_source_id everywhere; provider is
still carried alongside it since connector_tokens stores it as a column.

Reconciled against Ahmed Ibrahim's DATA-01 SQL (005_connector_tables.sql),
which is now the source of truth for the real column shapes — three things
the ERD/README alone didn't make clear:
  1. `provider` is a strict Postgres ENUM (provider_enum), not a free string
     — see the Provider enum below for the exact 4 allowed values.
  2. `refresh_token_encrypted` is nullable — not every provider issues a
     refresh token, so StoredToken.refresh_token is now `str | None`.
  3. `expires_at` and `last_refreshed_at` are also nullable — StoredToken
     reflects that, and check_connection_status() below handles a token
     with no known expiry as valid-but-unverifiable rather than assuming
     a datetime is always present.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class Provider(StrEnum):
    """Mirrors Postgres's provider_enum exactly (001_extensions_and_enums.sql
    in Ahmed's DATA-01 deliverable). Any value outside this set will be
    rejected by the real database at the column level — validating here
    too means a typo surfaces as a clear Python error in tests, not a
    cryptic asyncpg/psycopg error at the real DB boundary.
    """

    GOOGLE_ADS = "googleads"
    META_ADS = "metaads"
    GOOGLE_ANALYTICS = "googleanalytics"
    CSV_DEMO = "csv_demo"


class TokenErrorKind(StrEnum):
    """Failure codes for store_oauth_token() / refresh_token().

    Values match the typed TokenError set both INT-01 §2.7 and the
    Connector Layer Report §6.4 describe.
    """

    INVALID_AUTH_CODE = "invalid_auth_code"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    REFRESH_DENIED = "refresh_denied"


class InvalidAuthCodeError(Exception):
    """Raised by a TokenExchanger when the provider rejects an auth code
    (expired, already used, or malformed)."""


class ProviderUnreachableError(Exception):
    """Raised by a TokenExchanger when the provider's OAuth endpoint can't
    be reached (network failure, 5xx, timeout)."""


class RefreshDeniedError(Exception):
    """Raised by a TokenExchanger when the provider rejects a refresh token
    (revoked by the user, or expired past the point of refresh)."""


@dataclass(frozen=True)
class StoredToken:
    """In-memory shape of a connector_tokens row.

    access_token / refresh_token are plaintext here — encryption is the
    concrete TokenRepository implementation's job at its own storage
    boundary (encrypt on save, decrypt on get), so the business logic in
    tokens.py never handles ciphertext or an encryption key directly.

    refresh_token / expires_at / last_refreshed_at are all nullable,
    matching connector_tokens' real columns — access_token_encrypted is the
    only NOT NULL token field in the actual schema.
    """

    data_source_id: UUID
    provider: Provider
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    last_refreshed_at: datetime | None


@dataclass(frozen=True)
class ExchangedToken:
    """What a provider's OAuth token endpoint hands back — for a fresh
    auth-code exchange or a refresh, the shape is identical.

    refresh_token and expires_at are optional for the same reason as
    StoredToken above — some providers' authorization-code grants don't
    return a refresh token or a fixed expiry at all.
    """

    access_token: str
    refresh_token: str | None
    expires_at: datetime | None


@dataclass(frozen=True)
class ConnectionStatus:
    """check_connection_status() response.

    Deliberately has no error path (INT-01 §2.7: "never errors, reports
    connected: false instead") — a missing or expired token just produces
    connected=False / token_valid=False, never an exception.
    """

    connected: bool
    token_valid: bool
    last_successful_call_at: datetime | None


class TokenRepository(Protocol):
    """The storage boundary connector_tokens sits behind.

    A real SQLAlchemy-backed implementation is added once DATA-01's
    data_sources table (and this table's own Alembic migration) exist in
    main — deliberately deferred the same way CONN-01 left base.py
    unbuilt. InMemoryTokenRepository (repository.py) stands in for it now,
    for tests and as a concrete reference for the eventual real one.
    """

    def get(self, data_source_id: UUID) -> StoredToken | None: ...

    def save(self, token: StoredToken) -> None: ...


class TokenExchanger(Protocol):
    """The actual network call to a provider's OAuth token endpoint.

    Kept as an injected interface rather than a concrete HTTP client so the
    logic in tokens.py never needs real network access to be unit tested.
    A real implementation (Google's token endpoint today; GA4 in CONN-03)
    gets wired in alongside the repository.
    """

    def exchange_auth_code(self, provider: Provider, auth_code: str) -> ExchangedToken: ...

    def exchange_refresh_token(self, provider: Provider, refresh_token: str) -> ExchangedToken: ...
