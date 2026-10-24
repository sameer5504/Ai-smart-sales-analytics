from fastapi.testclient import TestClient

from app.main import app
from app.reports.service import save_report

client = TestClient(app)


def test_list_reports_requires_authentication():
    response = client.get("/api/reports")

    assert response.status_code == 401


def test_download_report_requires_authentication():
    response = client.get("/api/reports/download/some-id")

    assert response.status_code == 401


async def test_authenticated_user_lists_only_their_own_reports(
    tmp_path, monkeypatch, as_user
):
    monkeypatch.chdir(tmp_path)

    await save_report(user_id=1, data={"total": 100})
    await save_report(user_id=2, data={"total": 999})

    as_user(1)

    response = client.get("/api/reports")

    assert response.status_code == 200
    body = response.json()
    assert len(body["reports"]) == 1


async def test_owner_can_download_their_report(tmp_path, monkeypatch, as_user):
    monkeypatch.chdir(tmp_path)

    saved = await save_report(user_id=1, data={"total": 100})
    as_user(1)

    response = client.get(f"/api/reports/download/{saved.report_id}")

    assert response.status_code == 200
    assert response.json()["data"] == {"total": 100}


async def test_user_cannot_download_another_users_report(
    tmp_path, monkeypatch, as_user
):
    monkeypatch.chdir(tmp_path)

    saved = await save_report(user_id=1, data={"total": 100})
    as_user(2)

    response = client.get(f"/api/reports/download/{saved.report_id}")

    assert response.status_code == 404


async def test_download_nonexistent_report_returns_404(tmp_path, monkeypatch, as_user):
    monkeypatch.chdir(tmp_path)

    as_user(1)

    response = client.get("/api/reports/download/does-not-exist")

    assert response.status_code == 404


def test_generate_report_requires_authentication():
    response = client.post("/api/reports", json={"data": {"total": 100}})

    assert response.status_code == 401


async def test_authenticated_user_can_generate_and_then_download_a_report(
    tmp_path, monkeypatch, as_user
):
    monkeypatch.chdir(tmp_path)
    as_user(1)

    dashboard_snapshot = {
        "kpis": [{"label": "Total Revenue", "value": "55,289 ILS"}],
        "revenue_over_time": [{"month": "Jan 2025", "value": 1200.0}],
        "top_products": [{"name": "Widget", "value": 345.0}],
    }

    generate_res = client.post("/api/reports", json={"data": dashboard_snapshot})

    assert generate_res.status_code == 200
    generated = generate_res.json()
    assert generated["user_id"] == 1
    assert generated["data"] == dashboard_snapshot

    list_res = client.get("/api/reports")
    assert list_res.status_code == 200
    reports = list_res.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["report_id"] == generated["report_id"]

    download_res = client.get(f"/api/reports/download/{generated['report_id']}")
    assert download_res.status_code == 200
    assert download_res.json()["data"] == dashboard_snapshot


async def test_generated_reports_are_isolated_per_user(tmp_path, monkeypatch, as_user):
    monkeypatch.chdir(tmp_path)

    as_user(1)
    client.post("/api/reports", json={"data": {"total": 100}})

    as_user(2)
    response = client.get("/api/reports")

    assert response.status_code == 200
    assert response.json()["reports"] == []
