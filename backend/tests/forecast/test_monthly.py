"""Tests for the monthly aggregation utilities."""

import pandas as pd

from app.forecast.contract import MonthlyPoint
from app.forecast.monthly import history_points, monthly_totals, next_month_start


def _daily(start, days, value=10.0):
    return pd.Series(value, index=pd.date_range(start, periods=days, freq="D"))


def test_monthly_totals_sums_complete_months():
    daily = _daily("2026-01-01", 31 + 28)  # full Jan + full Feb 2026
    monthly = monthly_totals(daily)
    assert list(monthly.index.strftime("%Y-%m")) == ["2026-01", "2026-02"]
    assert monthly.iloc[0] == 310.0  # 31 days * 10


def test_monthly_totals_drops_partial_edge_months():
    daily = _daily("2026-01-15", 60)  # mid-Jan to mid-Mar; only Feb is complete
    assert list(monthly_totals(daily).index.strftime("%Y-%m")) == ["2026-02"]


def test_monthly_totals_empty():
    assert monthly_totals(pd.Series(dtype="float64")).empty


def test_next_month_start_after_last_complete_month():
    daily = _daily("2026-01-01", 59)  # Jan + Feb complete
    assert next_month_start(monthly_totals(daily), daily) == pd.Timestamp("2026-03-01")


def test_next_month_start_falls_back_to_data_end_without_a_complete_month():
    daily = _daily("2026-01-05", 10)  # no complete month
    assert next_month_start(monthly_totals(daily), daily) == pd.Timestamp("2026-02-01")


def test_history_points_shape():
    points = history_points(monthly_totals(_daily("2026-01-01", 59)))
    assert all(isinstance(p, MonthlyPoint) for p in points)
    assert [p.month for p in points] == ["2026-01", "2026-02"]
