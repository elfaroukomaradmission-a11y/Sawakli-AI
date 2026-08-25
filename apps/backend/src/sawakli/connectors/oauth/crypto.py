"""Symmetric encryption for OAuth token values at rest.

Resolves Conflict #1 / #13 (token storage ownership, connector_tokens
schema): the Connector Layer owns encryption exclusively, matching the
AES-256 approach the Backend Layer report already assumed for
oauth_connections. Concretely: AES-256-GCM via the `cryptography` package.

The encryption key is loaded once from the CONNECTOR_TOKEN_ENCRYPTION_KEY
environment variable (32 raw bytes, base64-encoded) — see
`load_encryption_key()`. This module has no knowledge of what it's
encrypting or where it's stored; callers pass a plaintext token string in
and get back the ciphertext bytes to persist in connector_tokens'
access_token_encrypted / refresh_token_encrypted BYTEA columns, and back.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_KEY_ENV_VAR = "CONNECTOR_TOKEN_ENCRYPTION_KEY"
_KEY_SIZE_BYTES = 32  # AES-256
_NONCE_SIZE_BYTES = 12  # 96-bit nonce, the standard/recommended size for AES-GCM


class EncryptionKeyError(RuntimeError):
    """Raised when the encryption key is missing, malformed, or the wrong size."""


def generate_encryption_key() -> str:
    """Generate a new base64-encoded 32-byte key, for seeding a local .env
    or a deployment secret. Not used at runtime — a convenience for setup.
    """
    return base64.b64encode(os.urandom(_KEY_SIZE_BYTES)).decode("ascii")


def load_encryption_key(env: dict[str, str] | None = None) -> bytes:
    """Load and validate the AES-256 key from the environment.

    Accepts an explicit `env` mapping for testing; defaults to `os.environ`.
    Raises EncryptionKeyError with an actionable message rather than letting
    a missing/malformed key surface as a confusing crypto exception later.
    """
    source = env if env is not None else os.environ
    raw = source.get(_KEY_ENV_VAR)
    if not raw:
        raise EncryptionKeyError(
            f"{_KEY_ENV_VAR} is not set. Generate one with "
            "crypto.generate_encryption_key() and add it to your .env."
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise EncryptionKeyError(f"{_KEY_ENV_VAR} is not valid base64.") from exc
    if len(key) != _KEY_SIZE_BYTES:
        raise EncryptionKeyError(
            f"{_KEY_ENV_VAR} must decode to exactly {_KEY_SIZE_BYTES} bytes "
            f"for AES-256 (got {len(key)})."
        )
    return key


def encrypt_token(plaintext: str, key: bytes) -> bytes:
    """Encrypt a token value for storage.

    Returns nonce || ciphertext (nonce prepended) as a single blob so the
    caller only has to persist one column — no separate nonce column needed.
    A fresh random nonce is used every call, per AES-GCM's requirements.
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_token(blob: bytes, key: bytes) -> str:
    """Reverse of encrypt_token().

    Raises ValueError if the blob is too short to contain a nonce, or if
    decryption fails (wrong key, or the ciphertext was tampered with —
    AES-GCM authenticates the ciphertext, so corruption is detected, not
    silently accepted).
    """
    if len(blob) < _NONCE_SIZE_BYTES:
        raise ValueError("Encrypted blob is too short to contain a nonce.")
    nonce, ciphertext = blob[:_NONCE_SIZE_BYTES], blob[_NONCE_SIZE_BYTES:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
