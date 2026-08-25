import base64

import pytest
from cryptography.exceptions import InvalidTag

from sawakli.connectors.oauth.crypto import (
    EncryptionKeyError,
    decrypt_token,
    encrypt_token,
    generate_encryption_key,
    load_encryption_key,
)

VALID_KEY = base64.b64encode(b"0" * 32).decode("ascii")


# --- load_encryption_key() ---


def test_load_key_success():
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    assert key == b"0" * 32


def test_load_key_missing():
    with pytest.raises(EncryptionKeyError, match="not set"):
        load_encryption_key({})


def test_load_key_not_base64():
    with pytest.raises(EncryptionKeyError, match="valid base64"):
        load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": "not-valid-base64!!"})


def test_load_key_wrong_length():
    too_short = base64.b64encode(b"0" * 16).decode("ascii")  # AES-128 size, not AES-256
    with pytest.raises(EncryptionKeyError, match="32 bytes"):
        load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": too_short})


def test_generate_encryption_key_is_loadable():
    generated = generate_encryption_key()
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": generated})
    assert len(key) == 32


# --- encrypt_token() / decrypt_token() ---


def test_round_trip():
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    blob = encrypt_token("ya29.a0AfH6SMC...", key)
    assert decrypt_token(blob, key) == "ya29.a0AfH6SMC..."


def test_ciphertext_is_not_plaintext():
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    secret = "super-secret-refresh-token"
    blob = encrypt_token(secret, key)
    assert secret.encode("utf-8") not in blob


def test_encrypting_twice_gives_different_ciphertext():
    """Each call uses a fresh random nonce, so identical plaintext never
    produces identical ciphertext — avoids leaking which rows share a value."""
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    first = encrypt_token("same-token", key)
    second = encrypt_token("same-token", key)
    assert first != second
    assert decrypt_token(first, key) == decrypt_token(second, key) == "same-token"


def test_decrypt_with_wrong_key_fails():
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    other_key = base64.b64decode(base64.b64encode(b"1" * 32))
    blob = encrypt_token("a-token", key)
    with pytest.raises(InvalidTag):
        decrypt_token(blob, other_key)


def test_decrypt_tampered_ciphertext_fails():
    """AES-GCM authenticates the ciphertext — corruption must be detected,
    not silently decrypted into garbage."""
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    blob = bytearray(encrypt_token("a-token", key))
    blob[-1] ^= 0xFF  # flip the last byte
    with pytest.raises(InvalidTag):
        decrypt_token(bytes(blob), key)


def test_decrypt_blob_too_short():
    key = load_encryption_key({"CONNECTOR_TOKEN_ENCRYPTION_KEY": VALID_KEY})
    with pytest.raises(ValueError, match="too short"):
        decrypt_token(b"short", key)
