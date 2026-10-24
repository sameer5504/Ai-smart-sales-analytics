"""Build a daily revenue series from the standardized sales DataFrame.

Every forecast model works on a daily revenue series (one revenue total per
calendar day). This adapter turns cleaned line items into that series and fills
gaps: a day inside the business's active date range with no transactions is
treated as **zero sales (closed)** rather than missing data, so day-of-week and
holiday patterns are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

DATE_COL = "transaction_date"
QUANTITY_COL = "quantity"
PRICE_COL = "unit_price"


@dataclass
class DailyRevenueSeries:
    """A daily revenue series plus a few quality counts.

    Attributes:
        series: revenue per calendar day, indexed by date (gaps filled with 0).
        start_date: first day in the series (None if empty).
        end_date: last day in the series (None if empty).
        days_total: number of calendar days covered (length of the series).
        days_with_sales: number of days that had at least one transaction.
        days_filled_zero: days inside the range with no transactions, filled with 0.
    """

    series: pd.Series
    start_date: pd.Timestamp | None
    end_date: pd.Timestamp | None
    days_total: int
    days_with_sales: int
    days_filled_zero: int

    def to_frame(self) -> pd.DataFrame:
        """Return a Prophet-style frame with ``ds`` (date) and ``y`` (revenue)."""
        return pd.DataFrame({"ds": self.series.index, "y": self.series.to_numpy()})

    def summary(self) -> str:
        if self.days_total == 0:
            return "Daily series: empty (no dated transactions)."
        return (
            f"Daily series: {self.days_total} days "
            f"({self.start_date.date()} to {self.end_date.date()}), "
            f"{self.days_with_sales} with sales, "
            f"{self.days_filled_zero} filled as zero."
        )


def build_daily_revenue_series(
    df: pd.DataFrame,
    *,
    date_col: str = DATE_COL,
    quantity_col: str = QUANTITY_COL,
    price_col: str = PRICE_COL,
) -> DailyRevenueSeries:
    """Aggregate standardized line items into a daily revenue series.

    Revenue per line is ``quantity * unit_price`` (net of returns, i.e. negative
    quantities reduce the day's total). Days are taken from the date part of
    ``transaction_date``; days inside the active range with no transactions are
    filled with 0.

    Args:
        df: the cleaned, standardized DataFrame.
        date_col / quantity_col / price_col: column names, for flexibility.

    Returns:
        A DailyRevenueSeries.

    Raises:
        TypeError: if ``df`` is not a pandas DataFrame.
        KeyError: if a required column is missing.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    missing = [c for c in (date_col, quantity_col, price_col) if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")

    # Revenue per line, and the calendar day it falls on (time-of-day dropped).
    revenue = df[quantity_col] * df[price_col]
    days = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()

    # Drop rows whose date could not be parsed.
    valid = days.notna()
    revenue = revenue[valid]
    days = days[valid]

    if len(days) == 0:
        empty = pd.Series(dtype="float64")
        empty.index = pd.DatetimeIndex([])
        return DailyRevenueSeries(empty, None, None, 0, 0, 0)

    # One total per day that had transactions.
    per_day = revenue.groupby(days).sum().sort_index()
    days_with_sales = len(per_day)

    # Fill every calendar day in the active range; missing days become 0 (closed).
    full_range = pd.date_range(per_day.index.min(), per_day.index.max(), freq="D")
    series = per_day.reindex(full_range, fill_value=0.0)
    series.index.name = "date"

    return DailyRevenueSeries(
        series=series,
        start_date=series.index[0],
        end_date=series.index[-1],
        days_total=len(series),
        days_with_sales=days_with_sales,
        days_filled_zero=len(series) - days_with_sales,
    )
