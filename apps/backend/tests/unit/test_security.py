from uuid import uuid4

from sawakli.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    password = "correct-password"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrong-password", hashed_password)


def test_access_token_contains_user_and_organization() -> None:
    user_id = uuid4()
    organization_id = uuid4()

    token = create_access_token(user_id, organization_id)

    decoded_user_id, decoded_organization_id = decode_access_token(token)

    assert decoded_user_id == user_id
    assert decoded_organization_id == organization_id
