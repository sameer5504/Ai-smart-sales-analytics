"""Daily Prophet forecast model (seasonality + holidays), summed to a month.

Fits Prophet on the daily revenue series with weekly + yearly seasonality and the
region's holiday calendar, forecasts the next full month's days, and sums them into
the monthly total. Kept as a per-business benchmark for the trained model.
Importing this module requires the optional ``prophet`` dependency.
"""

from __future__ import annotations

import logging

import pandas as pd
from prophet import Prophet

from app.forecast.contract import (
    MODEL_SEASONAL_HOLIDAY,
    REASON_INSUFFICIENT_HISTORY,
    ForecastResult,
    PredictionInterval,
)
from app.forecast.daily_series import DailyRevenueSeries
from app.forecast.holiday_calendar import holiday_calendar
from app.forecast.monthly import history_points, monthly_totals, next_month_start
from app.forecast.simple_models import MIN_MONTHS

# Prophet/Stan are chatty; keep the logs quiet.
logging.getLogger("prophet").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def daily_prophet_forecast(
    series: DailyRevenueSeries,
    *,
    region: str | None = None,
    custom_events: dict | None = None,
    min_months: int = MIN_MONTHS,
) -> ForecastResult:
    """Forecast next month's revenue with daily Prophet, summed to the month.

    Args:
        series: the daily revenue series.
        region: account region, used to pull the holiday calendar.
        custom_events: optional extra events for the calendar.
        min_months: guard; returns "unavailable" below this many complete months.
    """
    monthly = monthly_totals(series.series)
    target_start = next_month_start(monthly, series.series)

    if len(monthly) < min_months:
        return ForecastResult.unavailable(
            target_month=target_start.strftime("%Y-%m"),
            reason=REASON_INSUFFICIENT_HISTORY,
            message=(f"Need at least {min_months} months of history for a seasonal forecast; found {len(monthly)}."),
            history=history_points(monthly),
        )

    # Train only on complete months (drop the partial current month, if any).
    last_complete_end = (monthly.index[-1] + pd.offsets.MonthEnd(0)).normalize()
    train = series.series[series.series.index <= last_complete_end]
    frame = pd.DataFrame({"ds": train.index, "y": train.to_numpy()})

    # Holidays for every year the data or the target touches.
    holidays_df = None
    if region:
        years = sorted(set(train.index.year) | {target_start.year})
        calendar = holiday_calendar(region, years, custom_events=custom_events)
        if not calendar.empty:
            holidays_df = calendar

    model = Prophet(
        weekly_seasonality=True,
        yearly_seasonality=True,
        daily_seasonality=False,
        holidays=holidays_df,
    )
    model.fit(frame)

    # Predict the target month's days and sum them.
    days = pd.date_range(target_start, target_start + pd.offsets.MonthEnd(0), freq="D")
    predicted = model.predict(pd.DataFrame({"ds": days}))

    return ForecastResult.available(
        target_month=target_start.strftime("%Y-%m"),
        predicted_revenue=float(predicted["yhat"].sum()),
        model=MODEL_SEASONAL_HOLIDAY,
        history=history_points(monthly),
        interval=PredictionInterval(
            lower=float(predicted["yhat_lower"].sum()),
            upper=float(predicted["yhat_upper"].sum()),
        ),
    )
