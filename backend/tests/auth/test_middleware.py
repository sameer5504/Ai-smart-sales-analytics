from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_public_endpoint_does_not_require_token():
    response = client.get("/api/hello")

    assert response.status_code == 200


def test_protected_endpoint_rejects_missing_token():
    response = client.get("/auth/profile")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_protected_endpoint_rejects_malformed_authorization_header():
    response = client.get(
        "/auth/profile",
        headers={"Authorization": "InvalidToken"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials"


def test_protected_endpoint_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(
        "app.auth.middleware.verify_access_token",
        lambda token: "expired",
    )

    response = client.get(
        "/auth/profile",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token has expired"


def test_protected_endpoint_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(
        "app.auth.middleware.verify_access_token",
        lambda token: "invalid",
    )

    response = client.get(
        "/auth/profile",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_valid_token_sets_user_id_on_request_state(monkeypatch):
    monkeypatch.setattr(
        "app.auth.middleware.verify_access_token",
        lambda token: {"sub": "42"},
    )

    def fake_get_user_profile(user_id):
        assert user_id == 42
        return {
            "id": 42,
            "username": "testuser",
            "display_name": "Test User",
        }

    monkeypatch.setattr(
        "app.auth.router.get_user_profile",
        fake_get_user_profile,
    )

    response = client.get(
        "/auth/profile",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == 42


def test_jwt_error_response_keeps_cors_headers():
    response = client.get(
        "/auth/profile",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 401
    assert "access-control-allow-origin" in response.headers
