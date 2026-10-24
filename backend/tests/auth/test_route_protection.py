from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_profile_requires_authentication():
    response = client.get("/auth/profile")

    assert response.status_code == 401


def test_upload_requires_authentication():
    response = client.post(
        "/api/upload",
        files={
            "file": (
                "sales.csv",
                b"order_id,quantity\n1,2\n",
                "text/csv",
            )
        },
        data={"data_type": "sales"},
    )

    assert response.status_code == 401


def test_dashboard_requires_authentication():
    response = client.get("/api/dashboard/detailed", params={"filename": "sales.csv"})

    assert response.status_code == 401


def test_revenue_forecast_requires_authentication():
    response = client.get(
        "/api/forecast/revenue",
        params={"filename": "sales.csv"},
    )

    assert response.status_code == 401


def test_forecast_from_records_requires_authentication():
    response = client.post(
        "/api/forecast",
        json={"records": []},
    )

    assert response.status_code == 401


def test_chatbot_requires_authentication():
    response = client.post(
        "/chatbot/ask",
        json={
            "question": "What were my sales?",
            "history": [],
        },
    )

    assert response.status_code == 401


def test_reports_list_requires_authentication():
    response = client.get("/api/reports")

    assert response.status_code == 401


def test_reports_download_requires_authentication():
    response = client.get("/api/reports/download/some-id")

    assert response.status_code == 401


def test_login_remains_public():
    response = client.post(
        "/auth/login",
        json={},
    )

    # 422 comes from request validation, proving auth middleware
    # did not block the public endpoint with 401.
    assert response.status_code == 422


def test_register_remains_public():
    response = client.post(
        "/auth/register",
        json={},
    )

    assert response.status_code == 422


def test_refresh_remains_public(monkeypatch):
    monkeypatch.setattr(
        "app.auth.router.refresh_access_token",
        lambda token: {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "bearer",
        },
    )

    client.cookies.set(
        "refresh_token",
        "valid-refresh-token",
        path="/auth",
    )

    try:
        response = client.post("/auth/refresh")
    finally:
        client.cookies.clear()

    assert response.status_code == 200


def test_health_endpoint_remains_public():
    response = client.get("/api/hello")

    assert response.status_code == 200
