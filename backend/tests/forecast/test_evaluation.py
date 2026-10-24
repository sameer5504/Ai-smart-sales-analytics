"""Tests for the rolling-origin cross-validation helper."""

import math

import pandas as pd

from app.forecast.evaluation import expanding_backtest, rolling_origin_cv


def test_rolling_origin_cv_handles_a_zero_revenue_month():
    dates = pd.date_range("2022-01-01", "2022-06-30", freq="D")
    daily = pd.Series(100.0, index=dates)
    daily[daily.index.month == 6] = 0.0  # a full month with no revenue

    folds = rolling_origin_cv(daily, lambda history: 3000.0, cv_months=3)

    zero_month = folds.loc[folds["actual"] == 0]
    assert len(zero_month) == 1
    assert math.isnan(zero_month["ape"].iloc[0])
    # The undefined fold drops out of the MAPE instead of poisoning it.
    assert not math.isnan(folds["ape"].mean())


def test_rolling_origin_cv_keeps_ape_positive_for_a_month_net_of_returns():
    dates = pd.date_range("2022-01-01", "2022-03-31", freq="D")
    daily = pd.Series(100.0, index=dates)
    daily[daily.index.month == 3] = -10.0  # returns outweigh sales that month

    folds = rolling_origin_cv(daily, lambda history: 1000.0, cv_months=1)

    assert (folds["ape"] >= 0).all()


def test_expanding_backtest_scores_every_month_past_the_minimum():
    dates = pd.date_range("2022-01-01", "2022-06-30", freq="D")
    daily = pd.Series(100.0, index=dates)

    folds = expanding_backtest(daily, lambda history: 3000.0)

    # Six complete months, the first three held back as the minimum history.
    assert list(folds.index.strftime("%Y-%m")) == ["2022-04", "2022-05", "2022-06"]
    assert list(folds["nmonths"]) == [3, 4, 5]


def test_expanding_backtest_scores_nothing_without_enough_months():
    dates = pd.date_range("2022-01-01", "2022-03-31", freq="D")
    daily = pd.Series(100.0, index=dates)
    calls = []

    folds = expanding_backtest(daily, lambda history: calls.append(history) or 3000.0)

    # Three complete months is exactly the minimum, so there is no month left to
    # forecast and the forecaster is never called on an empty history.
    assert folds.empty
    assert calls == []
    assert list(folds.columns) == ["actual", "predicted", "ape", "nmonths"]
