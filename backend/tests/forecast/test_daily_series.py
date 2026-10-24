"""Tests for the daily revenue series adapter."""

import pandas as pd
import pytest

from app.forecast.daily_series import build_daily_revenue_series


def _df(rows):
    """rows: list of (transaction_date, quantity, unit_price)."""
    return pd.DataFrame(rows, columns=["transaction_date", "quantity", "unit_price"])


def test_revenue_is_quantity_times_price():
    result = build_daily_revenue_series(_df([("2026-01-01", 2, 10.0)]))
    assert result.series.iloc[0] == 20.0


def test_multiple_transactions_same_day_are_summed():
    result = build_daily_revenue_series(_df([("2026-01-01", 2, 10.0), ("2026-01-01", 1, 5.0)]))
    assert result.days_with_sales == 1
    assert result.series.iloc[0] == 25.0


def test_missing_days_filled_with_zero():
    # Jan 1 and Jan 3 have sales; Jan 2 has none -> filled with 0.
    result = build_daily_revenue_series(_df([("2026-01-01", 1, 10.0), ("2026-01-03", 1, 20.0)]))
    assert result.days_total == 3
    assert result.days_with_sales == 2
    assert result.days_filled_zero == 1
    assert result.series.loc["2026-01-02"] == 0.0


def test_time_component_is_dropped():
    result = build_daily_revenue_series(_df([("2026-01-01 09:30:00", 1, 10.0), ("2026-01-01 17:00:00", 1, 10.0)]))
    assert result.days_total == 1
    assert result.series.iloc[0] == 20.0


def test_returns_reduce_daily_revenue():
    # A return (negative quantity) nets against the sale on the same day.
    result = build_daily_revenue_series(_df([("2026-01-01", 5, 10.0), ("2026-01-01", -2, 10.0)]))
    assert result.series.iloc[0] == 30.0


def test_range_only_covers_active_dates():
    result = build_daily_revenue_series(_df([("2026-01-10", 1, 10.0), ("2026-01-12", 1, 10.0)]))
    assert result.start_date == pd.Timestamp("2026-01-10")
    assert result.end_date == pd.Timestamp("2026-01-12")


def test_empty_dataframe():
    result = build_daily_revenue_series(_df([]))
    assert result.days_total == 0
    assert result.days_with_sales == 0
    assert result.start_date is None
    assert len(result.series) == 0


def test_unparseable_dates_are_dropped():
    result = build_daily_revenue_series(_df([("2026-01-01", 1, 10.0), ("not a date", 1, 99.0)]))
    assert result.days_total == 1
    assert result.series.iloc[0] == 10.0


def test_to_frame_has_ds_and_y():
    result = build_daily_revenue_series(_df([("2026-01-01", 1, 10.0)]))
    frame = result.to_frame()
    assert list(frame.columns) == ["ds", "y"]
    assert frame.loc[0, "y"] == 10.0


def test_original_dataframe_not_mutated():
    df = _df([("2026-01-01", 2, 10.0)])
    build_daily_revenue_series(df)
    assert list(df.columns) == ["transaction_date", "quantity", "unit_price"]
    assert len(df) == 1


def test_invalid_input_type_raises():
    with pytest.raises(TypeError):
        build_daily_revenue_series([1, 2, 3])


def test_missing_column_raises():
    df = pd.DataFrame({"transaction_date": ["2026-01-01"], "quantity": [1]})
    with pytest.raises(KeyError):
        build_daily_revenue_series(df)


def test_summary_message():
    result = build_daily_revenue_series(_df([("2026-01-01", 1, 10.0), ("2026-01-03", 1, 20.0)]))
    assert "3 days" in result.summary()
    assert "filled as zero" in result.summary()
