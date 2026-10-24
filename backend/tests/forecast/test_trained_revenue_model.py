"""Tests for the trained revenue model and its transfer-ready features."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from app.forecast.trained_revenue_model import (
    FEATURE_NAMES,
    TrainedRevenueModel,
    build_features,
    detect_closed_days,
)


def _sample_series(days: int = 800, closed_weekday: int = 5) -> pd.Series:
    dates = pd.date_range("2021-01-01", periods=days, freq="D")
    base = 1000 + 300 * np.sin(np.arange(days) * 2 * np.pi / 365)  # yearly shape
    open_ = np.where(dates.dayofweek == closed_weekday, 0.0, 1.0)  # one closed day
    return pd.Series(base * open_, index=dates, name="revenue")


def test_detect_closed_days_finds_the_rest_day():
    assert detect_closed_days(_sample_series(closed_weekday=5)) == {5}  # Saturday
    assert detect_closed_days(_sample_series(closed_weekday=4)) == {4}  # Friday elsewhere


def test_build_features_returns_expected_columns():
    dates = pd.date_range("2022-01-01", periods=10, freq="D")
    features = build_features(dates, _sample_series(), baseline=1000.0, country="GB", closed_days={5})
    assert list(features.columns) == FEATURE_NAMES
    assert len(features) == 10
    assert features["is_closed_day"].isin([0, 1]).all()


def test_forecast_returns_a_full_month_of_positive_values():
    series = _sample_series()
    model = TrainedRevenueModel().fit(series, country="GB")
    result = model.forecast_next_month(series, country="GB")

    expected_month = (series.index.max() + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
    assert result.target_month == expected_month
    assert result.predicted_revenue > 0
    assert (result.daily >= 0).all()
    assert result.predicted_revenue == pytest.approx(result.daily.sum())


def test_forecast_rejects_a_series_with_no_recent_revenue():
    series = _sample_series()
    model = TrainedRevenueModel().fit(series, country="GB")
    series.iloc[-40:] = 0.0  # store closed for the whole baseline window

    with pytest.raises(ValueError, match="no baseline"):
        model.forecast_next_month(series, country="GB")


def test_country_changes_the_forecast():
    series = _sample_series()
    model = TrainedRevenueModel().fit(series, country="GB")
    gb = model.forecast_next_month(series, country="GB").predicted_revenue
    us = model.forecast_next_month(series, country="US").predicted_revenue
    assert gb != us  # a different holiday calendar changes the features, so the result


def test_save_and_load_roundtrip(tmp_path):
    series = _sample_series()
    model = TrainedRevenueModel().fit(series, country="GB")
    path = tmp_path / "model.joblib"
    model.save(str(path))

    loaded = TrainedRevenueModel.load(str(path))
    original = model.forecast_next_month(series, country="GB").predicted_revenue
    restored = loaded.forecast_next_month(series, country="GB").predicted_revenue
    assert restored == pytest.approx(original)
