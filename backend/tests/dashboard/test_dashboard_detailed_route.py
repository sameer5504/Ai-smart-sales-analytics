import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.dashboard.router as dashboard_router
from app.main import app

client = TestClient(app)

pytestmark = pytest.mark.usefixtures("authenticated_user")

# This router-level test cares about the row-shaping/dropping logic, not the
# ownership check itself (that's covered by the datasets_repository tests),
# so get_dataset_for_user is stubbed to always "find" this dataset for
# whichever user_id the auth fixture puts on the request.
FAKE_DATASET = {
    "id": 1,
    "user_id": 1,
    "filename": "sample.csv",
    "blob_path": "user-1/sample.csv",
    "row_count": 1,
    "stored": True,
    "created_at": "2026-07-01T00:00:00Z",
}


def _make_df(rows):
    """Helper: build a DataFrame shaped like what load_cleaned() returns."""
    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def _own_fake_dataset(monkeypatch, dataset=FAKE_DATASET):
    monkeypatch.setattr(dashboard_router, "get_dataset_for_user", lambda dataset_id, user_id: dataset)


def test_detailed_requires_dataset_id():
    response = client.get("/api/dashboard/detailed")
    assert response.status_code == 422


def test_detailed_returns_403_for_a_dataset_the_user_does_not_own(monkeypatch):
    monkeypatch.setattr(dashboard_router, "get_dataset_for_user", lambda dataset_id, user_id: None)

    response = client.get("/api/dashboard/detailed?dataset_id=999")

    assert response.status_code == 403


def test_detailed_returns_404_when_file_not_found(monkeypatch):
    _own_fake_dataset(monkeypatch)

    def fake_load_cleaned(user_id, filename):
        raise FileNotFoundError()

    monkeypatch.setattr(dashboard_router, "load_cleaned", fake_load_cleaned)

    response = client.get("/api/dashboard/detailed?dataset_id=1")

    assert response.status_code == 404
    assert response.json()["detail"] == "No data has been uploaded yet."


def test_detailed_returns_raw_rows_shape(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-01",
                "order_id": "O001",
                "product_id": "P001",
                "product_name": "Coffee 250g",
                "category": "Beverages",
                "quantity": 2,
                "unit_price": 15.0,
                "revenue": 30.0,
            }
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200
    assert body["data_quality"]["total_rows"] == 1

    row = body["data"][0]
    for key in (
        "date",
        "order_id",
        "product_id",
        "product_name",
        "category",
        "quantity",
        "unit_price",
        "revenue",
    ):
        assert key in row

    assert row["date"] == "2026-07-01"
    assert row["product_name"] == "Coffee 250g"


def test_detailed_defaults_missing_category_to_null(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-02",
                "order_id": "O002",
                "product_id": "P002",
                "product_name": "Za'atar 200g",
                "quantity": 1,
                "unit_price": 12.0,
                "revenue": 12.0,
            }
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200
    assert body["data_quality"]["total_rows"] == 1

    row = body["data"][0]
    assert row["category"] is None


def test_detailed_drops_rows_missing_order_id(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-03",
                "order_id": None,
                "product_id": "P003",
                "product_name": "Olive Oil 1L",
                "quantity": 1,
                "unit_price": 25.0,
                "revenue": 25.0,
            },
            {
                "transaction_date": "2026-07-04",
                "order_id": "O004",
                "product_id": "P004",
                "product_name": "Olive Oil 1L",
                "quantity": 1,
                "unit_price": 25.0,
                "revenue": 25.0,
            },
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200
    assert body["data_quality"]["total_rows"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["order_id"] == "O004"


def test_detailed_drops_rows_missing_product_id(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-05",
                "order_id": "O005",
                "product_id": None,
                "product_name": "Sumac 200g",
                "quantity": 1,
                "unit_price": 18.0,
                "revenue": 18.0,
            },
            {
                "transaction_date": "2026-07-06",
                "order_id": "O006",
                "product_id": "P006",
                "product_name": "Sumac 200g",
                "quantity": 1,
                "unit_price": 18.0,
                "revenue": 18.0,
            },
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200
    assert body["data_quality"]["total_rows"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["order_id"] == "O006"


def test_detailed_drops_rows_missing_core_numeric_fields(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-07",
                "order_id": "O007",
                "product_id": "P007",
                "product_name": "Sumac 200g",
                "quantity": None,  # core field missing -> row must be dropped
                "unit_price": 18.0,
                "revenue": None,
            },
            {
                "transaction_date": "2026-07-08",
                "order_id": "O008",
                "product_id": "P008",
                "product_name": "Sumac 200g",
                "quantity": 2,
                "unit_price": 18.0,
                "revenue": 36.0,
            },
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200  # no 500, bad row silently dropped
    assert body["data_quality"]["total_rows"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["order_id"] == "O008"


def test_detailed_total_rows_reflects_mixed_valid_and_dropped_rows(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-09",
                "order_id": "O009",
                "product_id": "P009",
                "product_name": "Coffee 250g",
                "quantity": 1,
                "unit_price": 15.0,
                "revenue": 15.0,
            },
            {
                "transaction_date": "2026-07-10",
                "order_id": "O010",
                "product_id": "P010",
                "product_name": "Tea 100g",
                "quantity": None,  # dropped
                "unit_price": 9.0,
                "revenue": None,
            },
            {
                "transaction_date": "2026-07-11",
                "order_id": "O011",
                "product_id": "P011",
                "product_name": "Honey 500g",
                "quantity": 2,
                "unit_price": 22.0,
                "revenue": 44.0,
            },
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200
    assert body["data_quality"]["total_rows"] == 2
    assert len(body["data"]) == 2
    order_ids = {row["order_id"] for row in body["data"]}
    assert order_ids == {"O009", "O011"}


def test_detailed_does_not_filter_zero_or_negative_values(monkeypatch):
    df = _make_df(
        [
            {
                "transaction_date": "2026-07-12",
                "order_id": "O012",
                "product_id": "P012",
                "product_name": "Sumac 200g",
                "quantity": 0,
                "unit_price": 18.0,
                "revenue": 0.0,
            },
            {
                "transaction_date": "2026-07-13",
                "order_id": "O013",
                "product_id": "P013",
                "product_name": "Dates 1kg",
                "quantity": 2,
                "unit_price": -20.0,
                "revenue": -40.0,
            },
        ]
    )

    _own_fake_dataset(monkeypatch)
    monkeypatch.setattr(dashboard_router, "load_cleaned", lambda user_id, filename: df)

    response = client.get("/api/dashboard/detailed?dataset_id=1")
    body = response.json()

    assert response.status_code == 200
    assert body["data_quality"]["total_rows"] == 2
    assert len(body["data"]) == 2
