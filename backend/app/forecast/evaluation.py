"""Rolling-origin cross-validation shared by the training, tuning, and ablation scripts.

One definition of "forecast each of the last months from the data before it" so the
train, tune, and feature-ablation scripts score models the same way.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from app.forecast.monthly import monthly_totals


def rolling_origin_cv(
    daily: pd.Series,
    predict: Callable[[pd.Series], float],
    *,
    cv_months: int = 6,
) -> pd.DataFrame:
    """Score a forecaster on the last ``cv_months`` complete months.

    For each month, ``predict(history)`` forecasts that month's total from the daily
    data before it. Returns a frame indexed by month with the actual total, the
    predicted total, and the absolute percentage error; callers average ``ape`` into a
    MAPE (and can read its spread across folds). ``ape`` is ``nan`` for a month whose
    actual total is zero, where a percentage error is undefined; pandas' mean skips it.
    """
    months = monthly_totals(daily)
    rows = {}
    for month in months.index[-cv_months:]:
        history = daily[daily.index < month]
        predicted = float(predict(history))
        actual = float(months.loc[month])
        # Divide by |actual| so returns-heavy months (negative total) still score positive.
        ape = abs(predicted - actual) / abs(actual) * 100 if actual else float("nan")
        rows[month] = (actual, predicted, ape)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["actual", "predicted", "ape"])


COLD_START_MONTHS = 12  # under a year of history counts as cold start
MIN_HISTORY_MONTHS = 3  # a few months are needed before a forecast is meaningful


def expanding_backtest(
    daily: pd.Series,
    predict: Callable[[pd.Series], float],
    *,
    min_history_months: int = MIN_HISTORY_MONTHS,
) -> pd.DataFrame:
    """Forecast every month from ``min_history_months`` onward, from the data before it.

    This scores a forecaster across the whole life of a series rather than only its last
    months, so cold-start and rich-history behaviour are both represented. Returns the
    :func:`rolling_origin_cv` frame plus an ``nmonths`` column (months of history
    available at each forecast).
    """
    months = monthly_totals(daily)
    cv_months = len(months) - min_history_months
    if cv_months <= 0:
        # Nothing to score: a negative or zero count would slice the whole index and
        # forecast months that have no history before them.
        return pd.DataFrame(columns=["actual", "predicted", "ape", "nmonths"])
    folds = rolling_origin_cv(daily, predict, cv_months=cv_months)
    position = {month: i for i, month in enumerate(months.index)}
    return folds.assign(nmonths=folds.index.map(position))


def mape_by_history(folds: pd.DataFrame, cold_start_months: int = COLD_START_MONTHS) -> tuple:
    """Split an expanding-backtest frame into (cold-start, rich-history, overall) MAPE."""
    cold = folds.loc[folds["nmonths"] < cold_start_months, "ape"].mean()
    rich = folds.loc[folds["nmonths"] >= cold_start_months, "ape"].mean()
    return float(cold), float(rich), float(folds["ape"].mean())
