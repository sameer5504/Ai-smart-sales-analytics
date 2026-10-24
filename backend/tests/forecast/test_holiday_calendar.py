"""Tests for the region-aware holiday calendar."""

from datetime import date

import pandas as pd

from app.forecast.holiday_calendar import (
    holiday_calendar,
    supported_regions,
)


def test_columns_are_prophet_shaped():
    cal = holiday_calendar("us", [2026])
    assert list(cal.columns) == ["holiday", "ds"]


def test_us_includes_christmas():
    cal = holiday_calendar("us", [2026])
    christmas = cal[cal["ds"] == pd.Timestamp("2026-12-25")]
    assert not christmas.empty
    assert "Christmas" in christmas.iloc[0]["holiday"]


def test_middle_east_has_holidays():
    cal = holiday_calendar("middle_east", [2026])
    assert not cal.empty  # Islamic + national holidays present


def test_unknown_region_returns_empty():
    cal = holiday_calendar("antarctica", [2026])
    assert cal.empty
    assert list(cal.columns) == ["holiday", "ds"]


def test_custom_events_are_added():
    cal = holiday_calendar("us", [2026], custom_events={date(2026, 11, 27): "White Friday"})
    match = cal[cal["holiday"] == "White Friday"]
    assert not match.empty
    assert match.iloc[0]["ds"] == pd.Timestamp("2026-11-27")


def test_multiple_years():
    cal = holiday_calendar("us", [2025, 2026])
    years = set(cal["ds"].dt.year)
    assert years == {2025, 2026}


def test_result_is_sorted_and_deduped():
    cal = holiday_calendar("middle_east", [2026])
    assert cal["ds"].is_monotonic_increasing
    assert not cal.duplicated().any()


def test_supported_regions():
    regions = supported_regions()
    assert "middle_east" in regions
    assert "us" in regions
