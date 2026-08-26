"""Reference TokenRepository implementation, plus the real Postgres one.

InMemoryTokenRepository is a real, working repository — it actually
encrypts on save and decrypts on get, using crypto.py — it just keeps rows
in a dict instead of Postgres. It exists so:

  1. tokens.py's functions have something concrete to run against in tests,
     beyond a bare mock.
  2. The encrypt-on-save / decrypt-on-get pattern a real Postgres-backed
     repository needs is written down and tested now, not guessed at later.

PostgresTokenRepository is the real one, backed by SQLAlchemy Core against
the actual connector_tokens table (see alembic/versions/0005_connector_tables.py,
ported from Ahmed Ibrahim's DATA-01 deliverable). Both implement the same
TokenRepository protocol, so swapping one for the other at the call site is
a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Connection
from sqlalchemy.dialects.postgresql import insert as pg_insert

from sawakli.db.tables import connector_tokens_table

from .crypto import decrypt_token, encrypt_token
from .models import Provider, StoredToken


@dataclass(frozen=True)
class _EncryptedRow:
    """What actually sits in memory — mirrors a real connector_tokens row's
    encrypted columns, so a decrypted token never lingers between calls."""

    provider: Provider
    access_token_encrypted: bytes
    refresh_token_encrypted: bytes | None
    expires_at: datetime | None
    last_refreshed_at: datetime | None


class InMemoryTokenRepository:
    """TokenRepository backed by a plain dict, keyed by data_source_id.

    Encrypted bytes are what's actually held in memory, mirroring what a
    real access_token_encrypted / refresh_token_encrypted BYTEA column
    would store — this repository never keeps a decrypted token around
    longer than the single get()/save() call that needs it.
    """

    def __init__(self, encryption_key: bytes) -> None:
        self._encryption_key = encryption_key
        self._rows: dict[UUID, _EncryptedRow] = {}

    def get(self, data_source_id: UUID) -> StoredToken | None:
        row = self._rows.get(data_source_id)
        if row is None:
            return None
        return StoredToken(
            data_source_id=data_source_id,
            provider=row.provider,
            access_token=decrypt_token(row.access_token_encrypted, self._encryption_key),
            refresh_token=(
                decrypt_token(row.refresh_token_encrypted, self._encryption_key)
                if row.refresh_token_encrypted is not None
                else None
            ),
            expires_at=row.expires_at,
            last_refreshed_at=row.last_refreshed_at,
        )

    def save(self, token: StoredToken) -> None:
        self._rows[token.data_source_id] = _EncryptedRow(
            provider=token.provider,
            access_token_encrypted=encrypt_token(token.access_token, self._encryption_key),
            refresh_token_encrypted=(
                encrypt_token(token.refresh_token, self._encryption_key)
                if token.refresh_token is not None
                else None
            ),
            expires_at=token.expires_at,
            last_refreshed_at=token.last_refreshed_at,
        )


class PostgresTokenRepository:
    """TokenRepository backed by the real connector_tokens table.

    Takes a live SQLAlchemy Connection rather than opening its own — the
    caller (Backend/Worker) owns connection/transaction lifecycle and
    should be using a role that only has grants on connector_tokens and
    read-only access to data_sources (connector_role, see
    007_security_roles_grants_rls.py), never a superuser connection.

    Encryption happens here, at the storage boundary, exactly like
    InMemoryTokenRepository — tokens.py's business logic never sees
    ciphertext or the encryption key.
    """

    def __init__(self, connection: Connection, encryption_key: bytes) -> None:
        self._conn = connection
        self._encryption_key = encryption_key

    def get(self, data_source_id: UUID) -> StoredToken | None:
        row = (
            self._conn.execute(
                connector_tokens_table.select().where(
                    connector_tokens_table.c.data_source_id == data_source_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return StoredToken(
            data_source_id=row["data_source_id"],
            provider=Provider(row["provider"]),
            access_token=decrypt_token(bytes(row["access_token_encrypted"]), self._encryption_key),
            refresh_token=(
                decrypt_token(bytes(row["refresh_token_encrypted"]), self._encryption_key)
                if row["refresh_token_encrypted"] is not None
                else None
            ),
            expires_at=row["expires_at"],
            last_refreshed_at=row["last_refreshed_at"],
        )

    def save(self, token: StoredToken) -> None:
        access_token_encrypted = encrypt_token(token.access_token, self._encryption_key)
        refresh_token_encrypted = (
            encrypt_token(token.refresh_token, self._encryption_key)
            if token.refresh_token is not None
            else None
        )
        # connector_tokens has a UNIQUE constraint on data_source_id (one
        # token row per connected account) — upsert on that, matching what
        # store_oauth_token() and refresh_token() both need: create on
        # first connect, overwrite in place on every later refresh.
        stmt = pg_insert(connector_tokens_table).values(
            data_source_id=token.data_source_id,
            provider=token.provider.value,
            access_token_encrypted=access_token_encrypted,
            refresh_token_encrypted=refresh_token_encrypted,
            expires_at=token.expires_at,
            last_refreshed_at=token.last_refreshed_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[connector_tokens_table.c.data_source_id],
            set_={
                "provider": stmt.excluded.provider,
                "access_token_encrypted": stmt.excluded.access_token_encrypted,
                "refresh_token_encrypted": stmt.excluded.refresh_token_encrypted,
                "expires_at": stmt.excluded.expires_at,
                "last_refreshed_at": stmt.excluded.last_refreshed_at,
            },
        )
        self._conn.execute(stmt)
