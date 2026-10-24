import jwt

import app.auth.jwt as jwt_service

TEST_SECRET = "test-secret-key"
TEST_ALGORITHM = "HS256"


def test_access_token_contains_expected_claims(monkeypatch):
    monkeypatch.setattr(
        jwt_service,
        "JWT_SECRET_KEY",
        TEST_SECRET,
    )
    monkeypatch.setattr(
        jwt_service,
        "JWT_ALGORITHM",
        TEST_ALGORITHM,
    )

    token = jwt_service.create_access_token(42)

    payload = jwt_service.verify_access_token(token)

    assert isinstance(payload, dict)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload


def test_verify_access_token_rejects_wrong_token_type(monkeypatch):
    monkeypatch.setattr(
        jwt_service,
        "JWT_SECRET_KEY",
        TEST_SECRET,
    )
    monkeypatch.setattr(
        jwt_service,
        "JWT_ALGORITHM",
        TEST_ALGORITHM,
    )

    token = jwt.encode(
        {
            "sub": "42",
            "type": "refresh",
        },
        TEST_SECRET,
        algorithm=TEST_ALGORITHM,
    )

    result = jwt_service.verify_access_token(token)

    assert result == "invalid"
