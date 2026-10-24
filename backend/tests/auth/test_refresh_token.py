from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app


def test_login_sets_http_only_refresh_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.auth.router.login_user",
        lambda username, password: {
            "id": 42,
            "username": username,
            "display_name": "Test User",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        },
    )

    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={
            "username": "testuser",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"] == "access-token"
    assert "refresh_token" not in body

    set_cookie = response.headers["set-cookie"]

    assert "refresh_token=refresh-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_register_sets_http_only_refresh_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.auth.router.register_user",
        lambda username, password: {
            "id": 42,
            "username": username,
            "display_name": "",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        },
    )

    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"] == "access-token"
    assert "refresh_token" not in body

    set_cookie = response.headers["set-cookie"]

    assert "refresh_token=refresh-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_refresh_endpoint_rotates_http_only_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.auth.router.refresh_access_token",
        lambda token: {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
        },
    )

    client = TestClient(app)

    client.cookies.set(
        "refresh_token",
        "old-refresh-token",
        path="/auth",
    )

    response = client.post("/auth/refresh")

    assert response.status_code == 200

    assert response.json() == {
        "access_token": "new-access-token",
        "token_type": "bearer",
    }

    assert "refresh_token" not in response.json()

    set_cookie = response.headers["set-cookie"]

    assert "refresh_token=new-refresh-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/auth" in set_cookie


def test_refresh_endpoint_rejects_invalid_cookie(monkeypatch):
    monkeypatch.setattr(
        "app.auth.router.refresh_access_token",
        lambda token: None,
    )

    client = TestClient(app)

    client.cookies.set(
        "refresh_token",
        "invalid-refresh-token",
        path="/auth",
    )

    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == ("Invalid or expired refresh token")


def test_refresh_endpoint_requires_refresh_cookie():
    client = TestClient(app)

    response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == ("Missing refresh token")


def test_logout_revokes_and_clears_refresh_cookie(
    monkeypatch,
):
    revoked_tokens = []

    monkeypatch.setattr(
        "app.auth.router.revoke_refresh_token",
        lambda token: revoked_tokens.append(token) or True,
    )

    client = TestClient(app)

    client.cookies.set(
        "refresh_token",
        "refresh-token-to-revoke",
        path="/auth",
    )

    response = client.post("/auth/logout")

    assert response.status_code == 200

    assert revoked_tokens == ["refresh-token-to-revoke"]

    set_cookie = response.headers["set-cookie"]

    assert "refresh_token=" in set_cookie
    assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie


class FakeCursor:
    def __init__(self, record):
        self.record = record
        self.rowcount = 0
        self.executed = []

    def execute(self, query, params):
        normalized_query = " ".join(query.split())
        self.executed.append((normalized_query, params))

        if normalized_query.startswith("UPDATE refresh_tokens"):
            self.rowcount = 1

    def fetchone(self):
        return self.record

    def close(self):
        pass


class FakeConnection:
    def __init__(self, record):
        self.cursor_instance = FakeCursor(record)
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        pass


def test_refresh_service_rejects_revoked_token(
    monkeypatch,
):
    from app.auth import service

    record = (
        42,
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
        datetime.now(timezone.utc).replace(tzinfo=None),
    )

    connection = FakeConnection(record)

    monkeypatch.setattr(
        service,
        "get_connection",
        lambda: connection,
    )

    result = service.refresh_access_token("revoked-refresh-token")

    assert result is None
    assert connection.committed is False


def test_refresh_service_rejects_expired_token(
    monkeypatch,
):
    from app.auth import service

    record = (
        42,
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        None,
    )

    connection = FakeConnection(record)

    monkeypatch.setattr(
        service,
        "get_connection",
        lambda: connection,
    )

    result = service.refresh_access_token("expired-refresh-token")

    assert result is None
    assert connection.committed is False


def test_refresh_service_rotates_refresh_token(
    monkeypatch,
):
    from app.auth import service

    record = (
        42,
        datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1),
        None,
    )

    connection = FakeConnection(record)

    monkeypatch.setattr(
        service,
        "get_connection",
        lambda: connection,
    )

    monkeypatch.setattr(
        service,
        "create_access_token",
        lambda user_id: (f"access-token-for-{user_id}"),
    )

    new_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)

    monkeypatch.setattr(
        service,
        "create_refresh_token",
        lambda: (
            "new-refresh-token",
            new_expiry,
        ),
    )

    monkeypatch.setattr(
        service,
        "hash_refresh_token",
        lambda token: f"hash:{token}",
    )

    result = service.refresh_access_token("old-refresh-token")

    assert result == {
        "access_token": "access-token-for-42",
        "refresh_token": "new-refresh-token",
        "token_type": "bearer",
    }

    queries = [query for query, _ in (connection.cursor_instance.executed)]

    assert any(("SELECT user_id, expires_at, revoked_at") in query and "FOR UPDATE" in query for query in queries)

    assert any(query.startswith("UPDATE refresh_tokens") for query in queries)

    assert any(query.startswith("INSERT INTO refresh_tokens") for query in queries)

    assert connection.committed is True
