"""Tests for the AutoML endpoint client and the fallback to the local model.

The endpoint is optional. It answers when it is configured and reachable; every other
case has to leave the local artifact serving the request, because a forecast the user
can see is better than an error when a remote service is down.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from app.forecast import automl_endpoint, service
from app.forecast.contract import MODEL_AUTOML, MODEL_TRAINED
from app.forecast.trained_revenue_model import MonthlyForecast


def sales_records(days: int = 400) -> pd.DataFrame:
    """A daily trading pattern long enough to clear the minimum-history rule."""
    dates = pd.date_range("2023-01-01", periods=days, freq="D")
    revenue = np.where(dates.dayofweek == 5, 0.0, 900.0 + 40.0 * (dates.dayofyear % 7))
    return pd.DataFrame(
        {
            "transaction_date": dates,
            "quantity": 1,
            "unit_price": revenue,
        }
    )


@pytest.fixture
def configured(local_model_only, monkeypatch):
    """Point the client at an unreachable URL, after conftest has cleared the real one.

    Depending on ``local_model_only`` explicitly fixes the ordering: the autouse fixture
    deletes the variables, then this one sets the test values.
    """
    monkeypatch.setenv(automl_endpoint.ENDPOINT_URL, "https://example.invalid/score")
    monkeypatch.setenv(automl_endpoint.ENDPOINT_KEY, "test-key")


def test_not_configured_without_both_variables(local_model_only, monkeypatch):
    monkeypatch.delenv(automl_endpoint.ENDPOINT_URL, raising=False)
    monkeypatch.setenv(automl_endpoint.ENDPOINT_KEY, "test-key")
    assert not automl_endpoint.is_configured()


def test_returns_none_when_not_configured(local_model_only):
    series = pd.Series(1.0, index=pd.date_range("2023-01-01", periods=100, freq="D"))
    assert automl_endpoint.forecast_next_month(series) is None


def test_request_frame_matches_the_trained_schema(configured):
    series = pd.Series(
        np.linspace(100.0, 200.0, 500),
        index=pd.date_range("2023-01-01", periods=500, freq="D"),
    )
    days = pd.date_range("2024-06-01", periods=30, freq="D")
    frame = automl_endpoint._endpoint_frame(days, series, "GB")

    assert list(frame.columns) == [
        "date",
        "month",
        "day",
        "weekofyear",
        "is_closed_day",
        "is_holiday",
        "is_holiday_eve",
        "is_after_holiday",
        "days_to_holiday",
        "days_from_holiday",
        "lag364",
    ]
    assert len(frame) == len(days)
    # The asset the endpoint trained on predates weekday_ratio.
    assert "weekday_ratio" not in frame.columns
    # lag364 is a raw amount there, not a ratio to the baseline.
    assert "lag364_ratio" not in frame.columns


def test_scales_the_answer_back_to_the_business(configured, monkeypatch):
    """A business a hundredth the size gets a forecast a hundredth the size."""
    captured = {}

    def fake_post(payload):
        captured["rows"] = payload["input_data"]["data"]
        return [automl_endpoint.TRAINING_BASELINE] * 31

    monkeypatch.setattr(automl_endpoint, "_post", fake_post)

    big = pd.Series(1000.0, index=pd.date_range("2023-01-01", periods=400, freq="D"))
    small = big / 100.0

    from_big = automl_endpoint.forecast_next_month(big)
    from_small = automl_endpoint.forecast_next_month(small)

    assert from_big is not None and from_small is not None
    assert from_big.predicted_revenue == pytest.approx(from_small.predicted_revenue * 100.0)


def test_falls_back_when_the_endpoint_errors(configured, monkeypatch):
    def explode(payload):
        raise OSError("connection refused")

    monkeypatch.setattr(automl_endpoint, "_post", explode)

    series = pd.Series(1000.0, index=pd.date_range("2023-01-01", periods=400, freq="D"))
    assert automl_endpoint.forecast_next_month(series) is None


def test_falls_back_when_the_endpoint_returns_the_wrong_number_of_days(configured, monkeypatch):
    monkeypatch.setattr(automl_endpoint, "_post", lambda payload: [1.0, 2.0])

    series = pd.Series(1000.0, index=pd.date_range("2023-01-01", periods=400, freq="D"))
    assert automl_endpoint.forecast_next_month(series) is None


def test_service_uses_the_local_model_when_the_endpoint_is_absent(local_model_only):
    result = service.forecast_from_dataframe(sales_records(), region="europe")

    assert result.status == "available"
    assert result.model == MODEL_TRAINED


def test_service_prefers_the_endpoint_when_it_answers(configured, monkeypatch):
    def answer(series, country="GB"):
        days = pd.date_range("2024-02-01", periods=29, freq="D")
        return MonthlyForecast(
            target_month="2024-02",
            predicted_revenue=12345.0,
            daily=pd.Series(1.0, index=days),
        )

    monkeypatch.setattr(automl_endpoint, "forecast_next_month", answer)

    result = service.forecast_from_dataframe(sales_records(), region="europe")

    assert result.model == MODEL_AUTOML
    assert result.predicted_revenue == pytest.approx(12345.0)


def test_service_falls_back_when_the_endpoint_cannot_answer(configured, monkeypatch):
    monkeypatch.setattr(automl_endpoint, "forecast_next_month", lambda series, country="GB": None)

    result = service.forecast_from_dataframe(sales_records(), region="europe")

    assert result.status == "available"
    assert result.model == MODEL_TRAINED


class _Response:
    """The little of urlopen's context manager that the client actually uses."""

    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_retries_when_the_endpoint_rejects_a_concurrent_request(configured, monkeypatch):
    """A 429 is a timing accident, not a reason to serve a worse forecast."""
    import json
    import urllib.error

    attempts = []

    def flaky(request, timeout=None):
        attempts.append(1)
        if len(attempts) < 3:
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)
        return _Response(json.dumps([automl_endpoint.TRAINING_BASELINE] * 31).encode())

    monkeypatch.setattr(automl_endpoint.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(automl_endpoint.urllib.request, "urlopen", flaky)

    series = pd.Series(1000.0, index=pd.date_range("2023-01-01", periods=400, freq="D"))
    result = automl_endpoint.forecast_next_month(series)

    assert result is not None, "the third attempt succeeded, so a forecast is expected"
    assert len(attempts) == 3


def test_gives_up_after_the_retry_budget(configured, monkeypatch):
    import urllib.error

    attempts = []

    def always_busy(request, timeout=None):
        attempts.append(1)
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(automl_endpoint.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(automl_endpoint.urllib.request, "urlopen", always_busy)

    series = pd.Series(1000.0, index=pd.date_range("2023-01-01", periods=400, freq="D"))
    assert automl_endpoint.forecast_next_month(series) is None
    assert len(attempts) == automl_endpoint.RETRY_ATTEMPTS
