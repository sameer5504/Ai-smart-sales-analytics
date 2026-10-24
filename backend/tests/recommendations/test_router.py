"""Route tests for GET /api/recommendations.

Three things are being checked. The route is behind auth and will not serve a
dataset the caller does not own, it hands back whatever the provider gives it
without reshaping it, and the absence cases come back the way the contract
says: an unprepared dataset is a 404, and having nothing to recommend is a 200
carrying a reason.

Ownership is stubbed here the same way the dashboard route tests stub it. What
these cover is that the check happens and that a failure is a 403, not the
repository query itself.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.recommendations.router as recommendations_router
from app.main import app
from app.recommendations.contract import RecommendationsResult
from app.recommendations.provider import (
    FIXTURES_ENV_VAR,
    get_recommendations_provider,
)
from tests.fixtures import recommendations as fixtures

client = TestClient(app)

DATASET_ID = 7

FAKE_DATASET = {
    "id": DATASET_ID,
    "user_id": 1,
    "filename": "sales.csv",
    "blob_path": "datasets/user-1/a1b2c3d4_sales.csv",
    "row_count": 1,
    "stored": True,
    "currency": "GBP",
    "created_at": "2026-07-01T00:00:00Z",
}

PREPARED_ROWS = pd.DataFrame(
    [
        {
            "transaction_date": pd.Timestamp("2026-07-20"),
            "order_id": "1001",
            "product_id": "P001",
            "quantity": 2.0,
            "unit_price": 45.0,
            "revenue": 90.0,
        }
    ]
)


@pytest.fixture
def owns_the_dataset(monkeypatch):
    monkeypatch.setattr(
        recommendations_router,
        "get_dataset_for_user",
        lambda dataset_id, user_id: FAKE_DATASET,
    )


@pytest.fixture
def owns_nothing(monkeypatch):
    monkeypatch.setattr(
        recommendations_router,
        "get_dataset_for_user",
        lambda dataset_id, user_id: None,
    )


@pytest.fixture
def prepared_rows(monkeypatch):
    """Stand in for this user's stored rows."""
    monkeypatch.setattr(
        "app.recommendations.provider.load_cleaned",
        lambda user_id, stored_filename: PREPARED_ROWS,
    )


@pytest.fixture
def no_prepared_rows(monkeypatch):
    def missing(user_id, stored_filename):
        raise FileNotFoundError("no prepared data")

    monkeypatch.setattr("app.recommendations.provider.load_cleaned", missing)


@pytest.fixture
def empty_rows(monkeypatch):
    monkeypatch.setattr(
        "app.recommendations.provider.load_cleaned",
        lambda user_id, stored_filename: PREPARED_ROWS.iloc[0:0],
    )


@pytest.fixture
def serve():
    """Install a provider for the route to call."""

    def _serve(provider):
        app.dependency_overrides[get_recommendations_provider] = lambda: provider

    try:
        yield _serve
    finally:
        app.dependency_overrides.pop(get_recommendations_provider, None)


def _get(dataset_id=DATASET_ID):
    return client.get("/api/recommendations", params={"dataset_id": dataset_id})


def test_recommendations_requires_authentication():
    assert _get().status_code == 401


def test_recommendations_requires_a_dataset_id(authenticated_user):
    assert client.get("/api/recommendations").status_code == 422


def test_a_dataset_the_user_does_not_own_is_refused(authenticated_user, owns_nothing):
    response = _get(999)

    assert response.status_code == 403
    assert "access" in response.json()["detail"].lower()


def test_someone_else_s_dataset_is_never_read(authenticated_user, owns_nothing, monkeypatch):
    """The refusal happens before anything touches storage."""
    read = []

    monkeypatch.setattr(
        "app.recommendations.provider.load_cleaned",
        lambda user_id, stored_filename: read.append(stored_filename),
    )

    _get(999)

    assert read == []


def test_the_rows_are_read_as_the_authenticated_user(authenticated_user, owns_the_dataset, serve, monkeypatch):
    """The user id comes from the request, and the name from the dataset row."""
    seen = {}

    def record(user_id, stored_filename):
        seen["user_id"] = user_id
        seen["stored_filename"] = stored_filename
        return PREPARED_ROWS

    monkeypatch.setattr("app.recommendations.provider.load_cleaned", record)
    serve(lambda df: fixtures.available_result())

    _get()

    assert seen["user_id"] == 1
    assert seen["stored_filename"] == "a1b2c3d4_sales.csv"


def test_recommendations_returns_the_provider_result(authenticated_user, owns_the_dataset, prepared_rows, serve):
    serve(lambda df: fixtures.available_result())

    response = _get()

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "available"
    assert len(body["recommendations"]) == len(fixtures.ALL_RECOMMENDATIONS)

    first = body["recommendations"][0]

    assert first["id"] == fixtures.COFFEE_DROP.id
    assert first["priority"] == 1
    assert first["finding"]["anomaly_type"] == "sharp_drop"
    assert first["evidence"]["current_value"] == 42.0
    assert first["expected_impact"]["confidence"] == "projected"


def test_recommendations_reports_what_the_cap_held_back(authenticated_user, owns_the_dataset, prepared_rows, serve):
    serve(lambda df: fixtures.capped_result())

    body = _get().json()

    assert body["total_findings"] == 20
    assert body["suppressed_count"] == 20 - len(body["recommendations"])


def test_an_unprepared_dataset_returns_404(authenticated_user, owns_the_dataset, no_prepared_rows):
    response = _get()

    assert response.status_code == 404
    assert "sales.csv" in response.json()["detail"]


def test_no_findings_returns_200_with_a_reason(authenticated_user, owns_the_dataset, prepared_rows, serve):
    serve(lambda df: fixtures.empty_result())

    response = _get()

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "unavailable"
    assert body["reason"] == "no_findings"
    assert body["message"]
    assert body["recommendations"] == []


def test_a_dataset_with_no_rows_returns_200_with_a_reason(authenticated_user, owns_the_dataset, empty_rows, serve):
    serve(_provider_that_must_not_run)

    response = _get()

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "unavailable"
    assert body["reason"] == "insufficient_history"
    assert body["message"]
    assert body["recommendations"] == []


def test_a_failing_provider_returns_200_with_a_reason(authenticated_user, owns_the_dataset, prepared_rows, serve):
    serve(_provider_that_fails)

    response = _get()

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "unavailable"
    assert body["reason"] == "detection_unavailable"
    assert body["message"]
    assert body["recommendations"] == []


def test_provider_defaults_to_the_engine_being_unavailable(monkeypatch):
    monkeypatch.delenv(FIXTURES_ENV_VAR, raising=False)

    result = get_recommendations_provider()(None)

    assert isinstance(result, RecommendationsResult)
    assert result.status == "unavailable"
    assert result.reason == "detection_unavailable"
    assert result.message
    assert result.recommendations == []


def test_provider_serves_fixtures_when_the_flag_is_set(monkeypatch):
    monkeypatch.setenv(FIXTURES_ENV_VAR, "1")

    result = get_recommendations_provider()(None)

    assert result.status == "available"
    assert result.recommendations


def _provider_that_fails(df):
    raise RuntimeError("detection blew up")


def _provider_that_must_not_run(df):
    raise AssertionError("the provider should not be called for an empty dataset")
