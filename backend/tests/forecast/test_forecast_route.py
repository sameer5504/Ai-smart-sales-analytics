"""Tests for the forecast endpoints, served by the trained revenue model.

``POST /api/forecast`` forecasts from records in the request body;
``GET /api/forecast/revenue`` forecasts from a prepared upload.
"""

import os

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.forecast.router as forecast_router
from app.auth.dependencies import get_current_user
from app.data_pipeline.preparation import prepare_upload
from app.forecast.router import router
from app.forecast.service import MODEL_PATH_ENV
from app.forecast.trained_revenue_model import TrainedRevenueModel

app = FastAPI()
app.include_router(router)
# These tests cover forecasting, not authentication. Route protection itself is
# covered in tests/auth/test_route_protection.py.
app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}
client = TestClient(app)

CONTRACT_KEYS = {
    "status",
    "target_month",
    "predicted_revenue",
    "currency",
    "model",
    "history",
    "interval",
    "reason",
    "message",
    "generated_at",
}

UPLOAD_HEADERS = [
    "Order Date",
    "Order No",
    "SKU",
    "Item",
    "Qty",
    "Unit Price",
    "Product Category",
]


@pytest.fixture(scope="module", autouse=True)
def trained_model(tmp_path_factory):
    """Train a small model, save it, and point the service at it for the tests."""
    dates = pd.date_range("2021-01-01", periods=800, freq="D")
    level = 1000 + 300 * np.sin(np.arange(800) * 2 * np.pi / 365)
    open_days = np.where(dates.dayofweek == 5, 0.0, 1.0)  # closed on Saturdays
    series = pd.Series(level * open_days, index=dates)

    path = tmp_path_factory.mktemp("model") / "revenue_model.joblib"
    TrainedRevenueModel().fit(series, country="GB").save(str(path))
    os.environ[MODEL_PATH_ENV] = str(path)
    yield
    os.environ.pop(MODEL_PATH_ENV, None)


def _records_for_months(n, start_year=2025):
    """Sales records giving n complete months (a sale on each month's 1st and last day)."""
    records = []
    for i, ms in enumerate(pd.date_range(f"{start_year}-01-01", periods=n, freq="MS")):
        month_end = ms + pd.offsets.MonthEnd(0)
        records.append({"transaction_date": ms.strftime("%Y-%m-%d"), "quantity": 1, "unit_price": 100.0 * (i + 1)})
        records.append({"transaction_date": month_end.strftime("%Y-%m-%d"), "quantity": 1, "unit_price": 50.0})
    return records


def _records_for_days(n, start="2025-01-01"):
    return [
        {"transaction_date": d.strftime("%Y-%m-%d"), "quantity": 1, "unit_price": 100.0}
        for d in pd.date_range(start, periods=n, freq="D")
    ]


# The authenticated_user fixture puts user_id 1 on every request, so uploads in
# these tests are prepared as that user and read back as that user.
USER_ID = 1

FAKE_DATASET = {
    "id": 1,
    "user_id": USER_ID,
    "filename": "sales.csv",
    "blob_path": "datasets/user-1/sales.csv",
    "row_count": 1,
    "stored": True,
    "created_at": "2026-07-01T00:00:00Z",
}


def _own_dataset(monkeypatch, filename="sales.csv", stored_filename=None):
    """Say the caller owns dataset 1, and that it points at ``filename``.

    The ownership rule itself belongs to the datasets_repository tests; these
    tests are about what the forecast route does once access is settled.
    """
    # Each upload is stored under its own blob name, so the display filename
    # and the stored one are not the same thing once a file has been uploaded
    # twice. Tests that actually prepare an upload pass the name it returned.
    dataset = {
        **FAKE_DATASET,
        "filename": filename,
        "blob_path": f"datasets/user-{USER_ID}/{stored_filename or filename}",
    }
    monkeypatch.setattr(forecast_router, "get_dataset_for_user", lambda dataset_id, user_id: dataset)


def _own_nothing(monkeypatch):
    monkeypatch.setattr(forecast_router, "get_dataset_for_user", lambda dataset_id, user_id: None)


def _write_upload(directory, name="sales.csv", days=90, start="2025-01-01"):
    """Write an uploaded sales file with one sale a day, in a business's own headings."""
    rows = [
        [day.strftime("%Y-%m-%d"), f"ORD-{i}", "P-100", "Widget", 2, 25.0, "Tools"]
        for i, day in enumerate(pd.date_range(start, periods=days, freq="D"))
    ]
    path = directory / name
    pd.DataFrame(rows, columns=UPLOAD_HEADERS).to_csv(path, index=False)
    return str(path)


def test_forecast_available_with_enough_history():
    resp = client.post("/api/forecast", json={"records": _records_for_months(8)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert body["predicted_revenue"] is not None
    assert body["model"] == "trained_revenue"
    assert "history" in body


def test_forecast_unavailable_with_too_little_history():
    resp = client.post("/api/forecast", json={"records": _records_for_days(10)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["reason"] == "insufficient_history"


def test_forecast_empty_records():
    resp = client.post("/api/forecast", json={"records": []})
    assert resp.status_code == 200
    assert resp.json()["status"] == "unavailable"


def test_forecast_unavailable_when_recent_window_has_no_revenue():
    on_the_books = [
        {"transaction_date": d.strftime("%Y-%m-%d"), "quantity": 1, "unit_price": 100.0}
        for d in pd.date_range("2025-01-01", periods=40, freq="D")
    ]
    # 40 more days covered by the data but with nothing sold.
    closed = [
        {"transaction_date": d.strftime("%Y-%m-%d"), "quantity": 0, "unit_price": 0.0}
        for d in pd.date_range("2025-02-10", periods=40, freq="D")
    ]

    resp = client.post("/api/forecast", json={"records": on_the_books + closed})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["reason"] == "insufficient_history"


def test_forecast_accepts_country_override():
    resp = client.post("/api/forecast", json={"records": _records_for_months(8), "country": "US"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert body["model"] == "trained_revenue"


def test_response_matches_contract_keys():
    resp = client.post("/api/forecast", json={"records": _records_for_months(8)})
    assert set(resp.json()) == CONTRACT_KEYS


def test_target_month_is_the_month_after_the_data_regardless_of_availability():
    """Data ending mid-month names the same target month whether or not a forecast
    was produced, so an unavailable response cannot point at a different month."""
    long_enough = _records_for_days(120, start="2025-01-01")  # ends 2025-04-30
    mid_month = long_enough + [{"transaction_date": "2025-05-09", "quantity": 1, "unit_price": 100.0}]

    available = client.post("/api/forecast", json={"records": mid_month}).json()
    unavailable = client.post(
        "/api/forecast",
        json={"records": [{"transaction_date": "2025-05-09", "quantity": 1, "unit_price": 100.0}]},
    ).json()

    assert available["status"] == "available"
    assert unavailable["status"] == "unavailable"
    assert available["target_month"] == "2025-06"
    assert unavailable["target_month"] == "2025-06"


async def test_revenue_forecast_reads_the_prepared_upload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prepared = await prepare_upload(_write_upload(tmp_path), "sales", USER_ID)
    _own_dataset(monkeypatch, stored_filename=prepared.stored_filename)

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert body["predicted_revenue"] > 0
    assert body["model"] == "trained_revenue"
    # January to March are complete months in the upload; April is what it forecasts.
    assert [point["month"] for point in body["history"]] == ["2025-01", "2025-02", "2025-03"]
    assert body["target_month"] == "2025-04"


async def test_revenue_forecast_matches_the_contract_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prepared = await prepare_upload(_write_upload(tmp_path), "sales", USER_ID)
    _own_dataset(monkeypatch, stored_filename=prepared.stored_filename)

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert set(resp.json()) == CONTRACT_KEYS


async def test_revenue_forecast_accepts_a_country_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prepared = await prepare_upload(_write_upload(tmp_path), "sales", USER_ID)
    _own_dataset(monkeypatch, stored_filename=prepared.stored_filename)

    gb = client.get("/api/forecast/revenue", params={"dataset_id": 1})
    us = client.get("/api/forecast/revenue", params={"dataset_id": 1, "country": "US"})

    assert gb.status_code == us.status_code == 200
    # A different holiday calendar changes the features, so the forecast changes too.
    assert gb.json()["predicted_revenue"] != us.json()["predicted_revenue"]


async def test_revenue_forecast_reports_too_little_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prepared = await prepare_upload(_write_upload(tmp_path, days=10), "sales", USER_ID)
    _own_dataset(monkeypatch, stored_filename=prepared.stored_filename)

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["reason"] == "insufficient_history"


async def test_revenue_forecast_reports_a_missing_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(MODEL_PATH_ENV, str(tmp_path / "not_deployed.joblib"))
    prepared = await prepare_upload(_write_upload(tmp_path), "sales", USER_ID)
    _own_dataset(monkeypatch, stored_filename=prepared.stored_filename)

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["reason"] == "model_unavailable"
    assert body["predicted_revenue"] is None
    # The history is still worth drawing even when the forecast itself is missing.
    assert body["history"]


def test_revenue_forecast_rejects_prepared_data_without_the_needed_columns(tmp_path, monkeypatch, fake_storage):
    monkeypatch.chdir(tmp_path)
    _own_dataset(monkeypatch, filename="sparse.csv")
    # Prepared rows whose price column was never identified by column mapping.
    fake_storage._store[(USER_ID, "sparse.csv")] = b"transaction_date,quantity\n2025-01-01,2\n"

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert resp.status_code == 400
    assert "unit_price" in resp.json()["detail"]


def test_revenue_forecast_reports_a_file_that_was_never_prepared(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _own_dataset(monkeypatch, filename="never_uploaded.csv")

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert resp.status_code == 404


def test_revenue_forecast_refuses_a_dataset_the_user_does_not_own(tmp_path, monkeypatch):
    """Being logged in is not enough; the dataset has to belong to the caller."""
    monkeypatch.chdir(tmp_path)
    _own_nothing(monkeypatch)

    resp = client.get("/api/forecast/revenue", params={"dataset_id": 999})

    assert resp.status_code == 403
    assert "access" in resp.json()["detail"].lower()


def test_revenue_forecast_reads_only_the_calling_user_storage(tmp_path, monkeypatch):
    """The user_id handed to load_cleaned comes from the request, never the query."""
    monkeypatch.chdir(tmp_path)
    _own_dataset(monkeypatch)
    seen = {}

    def spy(user_id, stored_filename):
        seen.update(user_id=user_id, stored_filename=stored_filename)
        raise FileNotFoundError("not prepared")

    monkeypatch.setattr(forecast_router, "load_cleaned", spy)

    client.get("/api/forecast/revenue", params={"dataset_id": 1})

    assert seen == {"user_id": USER_ID, "stored_filename": "sales.csv"}


def test_revenue_forecast_requires_a_dataset_id():
    assert client.get("/api/forecast/revenue").status_code == 422
