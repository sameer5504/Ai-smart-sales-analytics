"""The trailing-sales demand estimate (US-4.3.5, fallback half).

Every figure a restocking suggestion carries comes from the business's own
rows, so these check the arithmetic against frames written out by hand rather
than against another calculation.
"""

import pandas as pd
import pytest

from app.recommendations.contract import DemandSource
from app.recommendations.demand import (
    REASON_INSUFFICIENT_HISTORY,
    REASON_NOT_IN_HISTORY,
    build_trailing_sales_estimates,
    lookup,
)


def frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """Build prepared rows from (date, product_id, quantity) tuples."""
    return pd.DataFrame(
        rows,
        columns=["transaction_date", "product_id", "quantity"],
    )


def monthly(product_id: str, months: dict[str, float]) -> list[tuple]:
    """One row per month, so a month's total is the number given."""
    return [(f"{month}-10", product_id, units) for month, units in months.items()]


def test_the_estimate_is_the_median_of_the_last_three_months():
    rows = monthly("P1", {"2026-04": 10, "2026-05": 100, "2026-06": 40})
    rows += [("2026-06-30", "P1", 0)]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 40.0
    assert estimates["P1"].source is DemandSource.TRAILING_SALES


def test_one_freak_month_does_not_set_the_quantity():
    steady = monthly("P1", {"2026-04": 40, "2026-05": 44, "2026-06": 400})
    steady += [("2026-06-30", "P1", 0)]

    estimates = build_trailing_sales_estimates(frame(steady))

    assert estimates["P1"].expected_units == 44.0


def test_months_before_the_window_are_ignored():
    rows = monthly(
        "P1",
        {
            "2026-01": 500,
            "2026-02": 500,
            "2026-03": 500,
            "2026-04": 10,
            "2026-05": 20,
            "2026-06": 30,
        },
    )
    rows += [("2026-06-30", "P1", 0)]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 20.0


def test_units_are_totalled_across_a_month():
    rows = [
        ("2026-04-02", "P1", 5),
        ("2026-04-20", "P1", 7),
        ("2026-05-02", "P1", 30),
        ("2026-06-02", "P1", 1),
        ("2026-06-30", "P1", 0),
    ]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 12.0


def test_an_unfinished_final_month_is_left_out():
    rows = monthly("P1", {"2026-04": 30, "2026-05": 30, "2026-06": 30})
    rows += [("2026-07-03", "P1", 2)]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 30.0
    assert estimates["P1"].period_start.isoformat() == "2026-07-01"
    assert estimates["P1"].period_end.isoformat() == "2026-07-31"


def test_a_month_the_data_runs_to_the_end_of_is_counted():
    rows = monthly("P1", {"2026-04": 90, "2026-05": 90})
    rows += [("2026-06-30", "P1", 10)]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 90.0
    assert estimates["P1"].period_start.isoformat() == "2026-07-01"


def test_a_month_with_no_sales_counts_as_zero():
    rows = monthly("P1", {"2026-04": 60, "2026-06": 20})
    rows += [("2026-06-30", "P2", 1)]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 20.0


def test_a_product_is_not_judged_against_months_before_it_existed():
    rows = [
        ("2026-04-10", "P1", 100),
        ("2026-05-10", "P1", 100),
        ("2026-06-10", "P1", 100),
        ("2026-06-10", "P2", 50),
        ("2026-06-30", "P2", 10),
    ]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P2"].expected_units == 60.0


def test_a_product_seen_only_in_the_unfinished_month_has_no_estimate():
    rows = monthly("P1", {"2026-04": 30, "2026-05": 30, "2026-06": 30})
    rows += [("2026-07-03", "P2", 8)]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P2"].expected_units is None
    assert estimates["P2"].unavailable_reason == REASON_INSUFFICIENT_HISTORY
    assert estimates["P2"].is_available is False


def test_returns_reduce_the_month_they_fall_in():
    # Without the return June is 50 and the median is 50, so this only passes
    # if the returned units came off June's total.
    rows = [
        ("2026-04-10", "P1", 10),
        ("2026-05-10", "P1", 50),
        ("2026-06-10", "P1", 50),
        ("2026-06-12", "P1", -20),
        ("2026-06-30", "P1", 0),
    ]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 30.0


def test_an_estimate_is_never_negative():
    rows = [
        ("2026-04-10", "P1", 5),
        ("2026-04-12", "P1", -30),
        ("2026-05-10", "P1", 5),
        ("2026-05-12", "P1", -30),
        ("2026-06-10", "P1", 5),
        ("2026-06-30", "P1", -30),
    ]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 0.0


def test_rows_missing_a_date_a_product_or_a_quantity_are_dropped():
    rows = [
        ("2026-04-10", "P1", 20),
        (None, "P1", 999),
        ("2026-05-10", None, 999),
        ("2026-05-10", "P1", None),
        ("2026-05-10", "P1", 20),
        ("2026-06-30", "P1", 20),
    ]

    estimates = build_trailing_sales_estimates(frame(rows))

    assert estimates["P1"].expected_units == 20.0
    assert set(estimates) == {"P1"}


def test_weekly_estimates_use_weekly_periods():
    rows = [
        ("2026-06-01", "P1", 10),
        ("2026-06-08", "P1", 30),
        ("2026-06-15", "P1", 20),
        ("2026-06-21", "P1", 0),
    ]

    estimates = build_trailing_sales_estimates(frame(rows), frequency="weekly")

    assert estimates["P1"].expected_units == 20.0
    assert estimates["P1"].period_start.isoformat() == "2026-06-22"


def test_an_unsupported_frequency_is_rejected():
    with pytest.raises(ValueError, match="daily"):
        build_trailing_sales_estimates(frame([]), frequency="daily")


def test_an_empty_frame_produces_nothing():
    assert build_trailing_sales_estimates(frame([])) == {}


def test_a_frame_without_the_columns_produces_nothing():
    df = pd.DataFrame({"transaction_date": ["2026-06-01"], "revenue": [10.0]})

    assert build_trailing_sales_estimates(df) == {}


def test_lookup_covers_a_product_the_data_never_saw():
    rows = monthly("P1", {"2026-04": 10, "2026-05": 10})
    rows += [("2026-06-30", "P1", 10)]

    estimator = lookup(build_trailing_sales_estimates(frame(rows)))

    assert estimator("P1").expected_units == 10.0
    assert estimator("P9").unavailable_reason == REASON_NOT_IN_HISTORY


def test_dates_carrying_a_utc_offset_are_read_at_their_own_wall_clock():
    """A file exported with offsets used to fail the completeness check."""
    rows = frame(
        [
            ("2026-04-10 10:00:00+03:00", "P1", 20),
            ("2026-05-10 10:00:00+03:00", "P1", 20),
            ("2026-06-10 10:00:00+03:00", "P1", 20),
            ("2026-06-30 23:00:00+03:00", "P1", 0),
        ]
    )

    estimates = build_trailing_sales_estimates(rows)

    assert estimates["P1"].expected_units == 20.0
    assert estimates["P1"].period_start.isoformat() == "2026-07-01"


def test_rows_with_different_offsets_are_all_kept():
    """Mixed offsets cannot share a column, so they are read as UTC."""
    rows = frame(
        [
            ("2026-04-10 10:00:00+03:00", "P1", 20),
            ("2026-05-10 10:00:00+02:00", "P1", 20),
            ("2026-06-10 10:00:00+03:00", "P1", 20),
            ("2026-06-30 20:00:00+03:00", "P1", 0),
        ]
    )

    estimates = build_trailing_sales_estimates(rows)

    assert estimates["P1"].expected_units == 20.0


def test_a_numeric_product_id_is_not_keyed_as_a_decimal():
    """A product_id column with a blank cell is read as a float by pandas."""
    rows = frame(
        [
            ("2026-04-10", 12345.0, 10),
            ("2026-05-10", 12345.0, 10),
            ("2026-06-30", 12345.0, 10),
            ("2026-06-30", None, 5),
        ]
    )

    estimates = build_trailing_sales_estimates(rows)

    assert set(estimates) == {"12345"}
    assert "12345.0" not in estimates


def test_a_product_id_that_is_not_a_whole_number_keeps_its_own_spelling():
    rows = frame(
        [
            ("2026-04-10", "SKU-1.5", 10),
            ("2026-05-10", "SKU-1.5", 10),
            ("2026-06-30", "SKU-1.5", 10),
        ]
    )

    assert set(build_trailing_sales_estimates(rows)) == {"SKU-1.5"}
