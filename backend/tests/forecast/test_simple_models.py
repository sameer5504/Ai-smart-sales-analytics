"""Tests for the simple forecast models (moving average, linear trend)."""

import pandas as pd

from app.forecast.contract import STATUS_AVAILABLE, STATUS_UNAVAILABLE
from app.forecast.daily_series import DailyRevenueSeries, build_daily_revenue_series
from app.forecast.simple_models import (
    linear_trend_forecast,
    moving_average_forecast,
)


def _series_from_monthly(totals, start_year=2026, start_month=1):
    """Build a DailyRevenueSeries of complete months, each summing to its total."""
    month_starts = pd.date_range(pd.Timestamp(start_year, start_month, 1), periods=len(totals), freq="MS")
    idx = pd.date_range(month_starts[0], month_starts[-1] + pd.offsets.MonthEnd(0), freq="D")
    s = pd.Series(0.0, index=idx)
    for month_start, total in zip(month_starts, totals):
        s.loc[month_start] = float(total)
    return DailyRevenueSeries(
        series=s,
        start_date=idx[0],
        end_date=idx[-1],
        days_total=len(idx),
        days_with_sales=len(totals),
        days_filled_zero=len(idx) - len(totals),
    )


def test_moving_average_predicts_mean_of_last_months():
    result = moving_average_forecast(_series_from_monthly([100, 200, 300]), window=3)
    assert result.status == STATUS_AVAILABLE
    assert result.model == "moving_average"
    assert result.predicted_revenue == 200.0
    assert result.target_month == "2026-04"


def test_moving_average_uses_only_window():
    # window 2 -> mean of last two months (200, 300) = 250
    result = moving_average_forecast(_series_from_monthly([100, 200, 300]), window=2)
    assert result.predicted_revenue == 250.0


def test_linear_trend_extends_the_line():
    # perfect upward line -> next point is 400
    result = linear_trend_forecast(_series_from_monthly([100, 200, 300]))
    assert result.status == STATUS_AVAILABLE
    assert result.model == "linear_trend"
    assert round(result.predicted_revenue, 6) == 400.0


def test_linear_trend_flat_series():
    result = linear_trend_forecast(_series_from_monthly([150, 150, 150]))
    assert round(result.predicted_revenue, 6) == 150.0


def test_unavailable_when_too_few_months():
    result = linear_trend_forecast(_series_from_monthly([100, 200]))  # 2 < 3
    assert result.status == STATUS_UNAVAILABLE
    assert result.reason == "insufficient_history"
    assert "3 months" in result.message
    assert result.predicted_revenue is None


def test_min_months_is_configurable():
    result = moving_average_forecast(_series_from_monthly([100, 200]), min_months=2)
    assert result.status == STATUS_AVAILABLE


def test_history_reflects_monthly_totals():
    result = linear_trend_forecast(_series_from_monthly([100, 200, 300]))
    assert [(p.month, p.revenue) for p in result.history] == [
        ("2026-01", 100.0),
        ("2026-02", 200.0),
        ("2026-03", 300.0),
    ]


def test_partial_edge_months_are_dropped():
    # Data runs mid-Jan to mid-Mar: Jan and Mar are partial, only Feb is complete.
    df = pd.DataFrame(
        [
            ("2026-01-15", 1, 100.0),
            ("2026-02-10", 1, 200.0),
            ("2026-03-20", 1, 300.0),
        ],
        columns=["transaction_date", "quantity", "unit_price"],
    )
    daily = build_daily_revenue_series(df)
    result = linear_trend_forecast(daily, min_months=1)

    assert len(result.history) == 1
    assert result.history[0].month == "2026-02"
    assert result.target_month == "2026-03"


def test_empty_series_is_unavailable():
    empty = build_daily_revenue_series(pd.DataFrame(columns=["transaction_date", "quantity", "unit_price"]))
    result = linear_trend_forecast(empty)
    assert result.status == STATUS_UNAVAILABLE
