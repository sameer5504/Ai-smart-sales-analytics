"""Tests for the forecast output contract."""

from app.forecast.contract import (
    MODEL_LINEAR_TREND,
    REASON_INSUFFICIENT_HISTORY,
    STATUS_AVAILABLE,
    STATUS_UNAVAILABLE,
    ForecastResult,
    MonthlyPoint,
    PredictionInterval,
)


def _history():
    return [MonthlyPoint("2026-01", 14000.0), MonthlyPoint("2026-02", 14800.0)]


def test_available_result_shape():
    result = ForecastResult.available(
        target_month="2026-03",
        predicted_revenue=15230.5,
        model=MODEL_LINEAR_TREND,
        history=_history(),
        currency="GBP",
        interval=PredictionInterval(14200.0, 16260.0),
    )
    data = result.to_dict()

    assert data["status"] == STATUS_AVAILABLE
    assert data["target_month"] == "2026-03"
    assert data["predicted_revenue"] == 15230.5
    assert data["model"] == "linear_trend"
    assert data["history"] == [
        {"month": "2026-01", "revenue": 14000.0},
        {"month": "2026-02", "revenue": 14800.0},
    ]
    assert data["interval"] == {"lower": 14200.0, "upper": 16260.0}
    assert data["reason"] is None
    assert data["generated_at"]  # timestamp is set


def test_unavailable_result_shape():
    result = ForecastResult.unavailable(
        target_month="2026-03",
        reason=REASON_INSUFFICIENT_HISTORY,
        message="Need at least 3 months of sales history to forecast; found 1.",
        history=[MonthlyPoint("2026-01", 14000.0)],
    )
    data = result.to_dict()

    assert data["status"] == STATUS_UNAVAILABLE
    assert data["predicted_revenue"] is None
    assert data["model"] is None
    assert data["interval"] is None
    assert data["reason"] == "insufficient_history"
    assert "3 months" in data["message"]
    assert len(data["history"]) == 1


def test_interval_is_optional():
    result = ForecastResult.available(
        target_month="2026-03",
        predicted_revenue=100.0,
        model=MODEL_LINEAR_TREND,
        history=_history(),
    )
    assert result.to_dict()["interval"] is None


def test_all_contract_keys_present():
    result = ForecastResult.unavailable(
        target_month="2026-03",
        reason=REASON_INSUFFICIENT_HISTORY,
        message="not enough data",
    )
    expected_keys = {
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
    assert set(result.to_dict()) == expected_keys
