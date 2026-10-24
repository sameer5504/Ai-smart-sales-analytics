"""Monthly aggregation utilities shared across the forecasting models.

Roll a daily revenue series up to complete monthly totals, find the month to
forecast, and shape the monthly history for the output contract.
"""

from __future__ import annotations

import pandas as pd

from app.forecast.contract import MonthlyPoint


def monthly_totals(daily: pd.Series) -> pd.Series:
    """Sum the daily series into monthly totals, dropping partial edge months.

    A month at the start or end that isn't fully covered by the data has an
    artificially low total that would distort a trend, so it is excluded from
    the series used to forecast.
    """
    if len(daily) == 0:
        return pd.Series(dtype="float64")

    monthly = daily.resample("MS").sum()  # indexed by month-start
    start, end = daily.index[0], daily.index[-1]

    # First month is complete only if the data starts on the 1st.
    if start.day != 1 and len(monthly) > 0:
        monthly = monthly.iloc[1:]
    # Last month is complete only if the data ends on that month's last day.
    if len(monthly) > 0 and end.normalize() != (end + pd.offsets.MonthEnd(0)).normalize():
        monthly = monthly.iloc[:-1]

    return monthly


def next_month_start(monthly: pd.Series, daily: pd.Series) -> pd.Timestamp:
    """First day of the month to forecast: after the last complete month (or after
    the data if there are no complete months, or today if there is no data)."""
    if len(monthly):
        reference = monthly.index[-1]
    elif len(daily):
        reference = daily.index[-1]
    else:
        reference = pd.Timestamp.today().normalize()
    return (reference + pd.offsets.MonthBegin(1)).normalize()


def history_points(monthly: pd.Series) -> list[MonthlyPoint]:
    """Shape a monthly-totals series into the contract's history points."""
    return [MonthlyPoint(month=ts.strftime("%Y-%m"), revenue=float(value)) for ts, value in monthly.items()]
