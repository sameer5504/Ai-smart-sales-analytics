"""Trained revenue forecast model with region-transferable features.

A single gradient-boosting model forecasts next month's total revenue from a daily
revenue series. Revenue is modelled as a ratio to the recent baseline, so what the
model learns are scale-free calendar effects (rest-day closures, the shape of the
trading week, holiday drops, the run-up before a holiday, yearly shape) rather than one
store's absolute numbers. Those effects carry to another store or country: the rest day
and the weekday profile are read from each store's own data and holidays come from its
region's calendar, so the trained model applies even though it trained on one region
with a different weekend.

The model is trained once and saved; serving loads the artifact and calls
``forecast_next_month`` with a series.
"""

from __future__ import annotations

from dataclasses import dataclass

import holidays as holidays_lib
import lightgbm as lgb
import numpy as np
import pandas as pd

BASELINE_WINDOW = 28  # scale baseline: four weeks (one weekly cycle)
LAGS_DAYS = 364  # same weekday one year back (52 weeks keeps the day-of-week aligned)

# Feature set chosen by the subset search in notebooks/revenue_forecasting_analysis.ipynb,
# scored on an expanding backtest split by history length. Recent momentum and the smooth
# seasonal encodings were both tested and lost; weekday_ratio won and is included here.
FEATURE_NAMES = [
    "month",
    "day",
    "weekofyear",
    "is_closed_day",
    "weekday_ratio",
    "is_holiday",
    "is_holiday_eve",
    "is_after_holiday",
    "days_to_holiday",
    "days_from_holiday",
    "lag364_ratio",
]

CLOSED_DAY_ZERO_FRACTION = 0.8  # a weekday closed on >=80% of days is a rest day

# Selected by the grid search in notebooks/revenue_forecasting_analysis.ipynb
# (rolling-origin cross-validation); that notebook re-derives and re-checks these
# values. Many shallow trees with a moderate learning rate beat the fewer, slower
# ones tried first: with three leaves each tree captures one effect at a time, so
# the ensemble stays additive rather than fitting interactions this much data
# cannot support. random_state is fixed so the saved artifact is reproducible.
DEFAULT_PARAMS = {
    "n_estimators": 1200,
    "learning_rate": 0.05,
    "num_leaves": 3,
    "min_child_samples": 40,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "random_state": 0,
    "verbose": -1,
}


@dataclass
class MonthlyForecast:
    """Next-month forecast: the total plus the daily breakdown it was summed from."""

    target_month: str  # "YYYY-MM"
    predicted_revenue: float
    daily: pd.Series


def _holiday_dates(country: str, years: list[int]) -> set[pd.Timestamp]:
    cal = holidays_lib.country_holidays(country, years=years)
    return {pd.Timestamp(d).normalize() for d in cal}


def detect_closed_days(daily: pd.Series) -> set[int]:
    """Weekdays the store is usually closed, inferred from its own data.

    Returns the weekday numbers (Mon=0) whose revenue is zero on at least
    ``CLOSED_DAY_ZERO_FRACTION`` of days. This adapts to each store's rest day
    instead of assuming a Western weekend, so a UK-trained model applies correctly
    to a region that rests on a different day.
    """
    zero_fraction = (daily == 0).groupby(daily.index.dayofweek).mean()
    return {int(dow) for dow, frac in zero_fraction.items() if frac >= CLOSED_DAY_ZERO_FRACTION}


def weekday_profile(daily: pd.Series) -> dict[int, float]:
    """Each weekday's average revenue as a ratio to the recent baseline.

    Read from the store's own history, so it describes how that store trades rather
    than assuming a Western trading week. It is the graded version of
    ``detect_closed_days``: a rest day lands near 0, a quiet weekday below 1, the
    store's busiest weekday above 1. Weekdays with no usable history fall back to 1.0.
    """
    baseline = daily.shift(1).rolling(BASELINE_WINDOW).mean()
    ratio = daily / baseline
    ratio = ratio[np.isfinite(ratio) & (baseline > 0)]
    averages = ratio.groupby(ratio.index.dayofweek).mean()
    profile = {}
    for dow in range(7):
        value = float(averages.get(dow, 1.0))
        profile[dow] = value if np.isfinite(value) else 1.0
    return profile


def build_features(
    dates: pd.DatetimeIndex,
    history: pd.Series,
    baseline: float | np.ndarray,
    country: str,
    closed_days: set[int],
) -> pd.DataFrame:
    """Build the model's features for ``dates``.

    All features come from the calendar, the region's holidays, and the store's own
    trading pattern, so they can be generated for any store or country. ``history``
    supplies last year's value and the weekday profile, and ``baseline`` is the recent
    average used to make the last-year value scale-free (a scalar for a single forecast
    origin, or one value per date when training).

    The weekday profile is a summary of the whole history, like the detected rest days,
    so a training row sees weekday averages drawn from days after it. That stays inside
    the forecast origin: at every backtest fold and at serving time, ``history`` ends
    before the month being predicted.
    """
    years = list(range(dates.year.min() - 1, dates.year.max() + 1))
    holidays_set = _holiday_dates(country, years)
    holiday_index = pd.DatetimeIndex(sorted(holidays_set))

    f = pd.DataFrame(index=dates)
    f["month"] = dates.month
    f["day"] = dates.day
    f["weekofyear"] = dates.isocalendar().week.astype(int).to_numpy()
    f["is_closed_day"] = dates.dayofweek.isin(closed_days).astype(int)
    f["weekday_ratio"] = dates.dayofweek.map(weekday_profile(history)).to_numpy()
    f["is_holiday"] = dates.isin(holidays_set).astype(int)
    f["is_holiday_eve"] = (dates + pd.Timedelta(days=1)).isin(holidays_set).astype(int)
    f["is_after_holiday"] = (dates - pd.Timedelta(days=1)).isin(holidays_set).astype(int)

    if len(holiday_index):
        pos = holiday_index.searchsorted(dates)
        to_next = [(holiday_index[min(p, len(holiday_index) - 1)] - d).days for p, d in zip(pos, dates)]
        from_last = [(d - holiday_index[max(p - 1, 0)]).days for p, d in zip(pos, dates)]
    else:
        to_next = from_last = [30] * len(dates)
    f["days_to_holiday"] = np.clip(to_next, 0, 30)
    f["days_from_holiday"] = np.clip(from_last, 0, 30)

    last_year = [history.get(d - pd.Timedelta(days=LAGS_DAYS), np.nan) for d in dates]
    f["lag364_ratio"] = np.asarray(last_year, dtype="float64") / baseline
    return f[FEATURE_NAMES]


class TrainedRevenueModel:
    """Gradient-boosting revenue model trained on ratio-to-baseline targets."""

    def __init__(self, params: dict | None = None):
        self.model = lgb.LGBMRegressor(**(params or DEFAULT_PARAMS))

    def _training_frame(self, daily: pd.Series, country: str, closed_days: set[int]) -> tuple[pd.DataFrame, np.ndarray]:
        baseline = daily.shift(1).rolling(BASELINE_WINDOW).mean().to_numpy()
        features = build_features(daily.index, daily, baseline, country, closed_days)
        target = daily.to_numpy() / baseline
        valid = np.isfinite(baseline) & (baseline > 0) & np.isfinite(target)
        return features[valid], target[valid]

    def fit(self, daily: pd.Series, country: str = "GB") -> TrainedRevenueModel:
        """Train on a daily revenue series. ``country`` selects the holiday calendar;
        rest days are detected from the series itself."""
        X, y = self._training_frame(daily, country, detect_closed_days(daily))
        self.model.fit(X, y)
        return self

    def forecast_next_month(self, daily: pd.Series, country: str = "GB") -> MonthlyForecast:
        """Forecast the month after the series ends.

        ``country`` selects the holiday calendar and the rest days are detected from
        the given series, so passing a different region's series and country applies
        the trained model there.
        """
        baseline = float(daily.iloc[-BASELINE_WINDOW:].mean())
        if not np.isfinite(baseline) or baseline <= 0:
            raise ValueError(
                f"No positive revenue in the last {BASELINE_WINDOW} days, so there is no baseline to forecast against."
            )
        start = (daily.index.max() + pd.offsets.MonthBegin(1)).normalize()
        days = pd.date_range(start, start + pd.offsets.MonthEnd(0), freq="D")
        features = build_features(days, daily, baseline, country, detect_closed_days(daily))
        predicted = np.clip(self.model.predict(features), 0, None) * baseline
        daily_pred = pd.Series(predicted, index=days, name="revenue")
        return MonthlyForecast(
            target_month=start.strftime("%Y-%m"),
            predicted_revenue=float(daily_pred.sum()),
            daily=daily_pred,
        )

    def save(self, path: str) -> None:
        import joblib

        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path: str) -> TrainedRevenueModel:
        import joblib

        instance = cls()
        instance.model = joblib.load(path)
        return instance
