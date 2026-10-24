"""Simple forecast models for businesses with limited history.

These run on **monthly** revenue totals (resampled from the daily series) and
forecast next month's total:

- moving average: mean of the last N months
- linear trend: least-squares line through the monthly totals, extended one month

Both return the shared ForecastResult contract, or an "unavailable" result when
there is too little history. The minimum-history and window values are configurable
defaults.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.forecast.contract import (
    MODEL_LINEAR_TREND,
    MODEL_MOVING_AVERAGE,
    REASON_INSUFFICIENT_HISTORY,
    ForecastResult,
)
from app.forecast.daily_series import DailyRevenueSeries
from app.forecast.monthly import history_points, monthly_totals, next_month_start

# Default thresholds.
MIN_MONTHS = 3
MOVING_AVERAGE_WINDOW = 3


def _next_month(monthly: pd.Series, daily: pd.Series) -> str:
    return next_month_start(monthly, daily).strftime("%Y-%m")


def _unavailable(monthly: pd.Series, daily: pd.Series, min_months: int) -> ForecastResult:
    return ForecastResult.unavailable(
        target_month=_next_month(monthly, daily),
        reason=REASON_INSUFFICIENT_HISTORY,
        message=(f"Need at least {min_months} months of sales history to forecast; found {len(monthly)}."),
        history=history_points(monthly),
    )


def moving_average_forecast(
    series: DailyRevenueSeries,
    *,
    window: int = MOVING_AVERAGE_WINDOW,
    min_months: int = MIN_MONTHS,
) -> ForecastResult:
    """Forecast next month's revenue as the mean of the last ``window`` months."""
    monthly = monthly_totals(series.series)
    if len(monthly) < min_months:
        return _unavailable(monthly, series.series, min_months)

    predicted = float(monthly.iloc[-window:].mean())
    return ForecastResult.available(
        target_month=_next_month(monthly, series.series),
        predicted_revenue=predicted,
        model=MODEL_MOVING_AVERAGE,
        history=history_points(monthly),
    )


def linear_trend_forecast(
    series: DailyRevenueSeries,
    *,
    min_months: int = MIN_MONTHS,
) -> ForecastResult:
    """Forecast next month by fitting a line to the monthly totals and extending
    it one month."""
    monthly = monthly_totals(series.series)
    if len(monthly) < min_months:
        return _unavailable(monthly, series.series, min_months)

    y = monthly.to_numpy(dtype="float64")
    if len(y) == 1:
        # A single month gives no slope; predict that value (flat).
        predicted = float(y[0])
    else:
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        predicted = float(slope * len(y) + intercept)

    return ForecastResult.available(
        target_month=_next_month(monthly, series.series),
        predicted_revenue=predicted,
        model=MODEL_LINEAR_TREND,
        history=history_points(monthly),
    )
