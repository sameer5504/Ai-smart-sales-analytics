"""Tests for the daily Prophet model.

Prophet is a heavy optional dependency and fitting is slow, so these tests are
skipped when it isn't installed and kept minimal.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("prophet")

from app.forecast.contract import STATUS_AVAILABLE, STATUS_UNAVAILABLE
from app.forecast.daily_series import DailyRevenueSeries
from app.forecast.prophet_model import daily_prophet_forecast


def _daily_series(months, start="2024-01-01"):
    """A daily series of `months` complete months with weekly seasonality."""
    start_ts = pd.Timestamp(start)
    end = start_ts + pd.offsets.MonthBegin(months) - pd.offsets.Day(1)
    idx = pd.date_range(start_ts, end, freq="D")
    y = 100 + np.arange(len(idx)) * 0.05 + 20 * np.sin(2 * np.pi * idx.dayofweek / 7)
    s = pd.Series(np.clip(y, 0, None), index=idx)
    return DailyRevenueSeries(s, idx[0], idx[-1], len(idx), len(idx), 0)


def test_returns_seasonal_forecast():
    result = daily_prophet_forecast(_daily_series(14))
    assert result.status == STATUS_AVAILABLE
    assert result.model == "seasonal_holiday"
    assert result.predicted_revenue > 0
    assert result.interval is not None
    assert result.target_month == "2025-03"  # month after 14 complete months
    assert len(result.history) == 14


def test_runs_with_region_holidays():
    result = daily_prophet_forecast(_daily_series(14), region="middle_east")
    assert result.status == STATUS_AVAILABLE
    assert result.predicted_revenue > 0


def test_too_little_history_is_unavailable():
    result = daily_prophet_forecast(_daily_series(3), min_months=12)
    assert result.status == STATUS_UNAVAILABLE
    assert result.reason == "insufficient_history"
