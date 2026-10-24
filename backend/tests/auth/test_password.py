"""Password hashing has to actually run.

The rest of the auth suite exercises tokens and route protection, none of
which touch passlib. That left the hashing backend itself untested, so an
incompatible bcrypt release could break registration and login while the
suite stayed green. These tests call the real functions.
"""

import pytest

from app.auth.password import hash_password, verify_password

PASSWORD = "correct-horse-battery-staple"


def test_hash_password_produces_a_bcrypt_hash():
    hashed = hash_password(PASSWORD)

    assert isinstance(hashed, str)
    assert hashed.startswith("$2")
    assert hashed != PASSWORD


def test_verify_password_accepts_the_original_password():
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_verify_password_rejects_a_wrong_password():
    assert verify_password("not-the-password", hash_password(PASSWORD)) is False


def test_each_hash_is_salted_differently():
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


@pytest.mark.parametrize(
    "password",
    [
        "short",
        "a-fairly-ordinary-password-123",
        "pässwörd-with-ünicode",
        "x" * 72,
    ],
)
def test_round_trip_for_a_range_of_passwords(password):
    assert verify_password(password, hash_password(password)) is True
