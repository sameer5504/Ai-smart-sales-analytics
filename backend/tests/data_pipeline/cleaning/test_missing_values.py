"""Tests for missing-value handling.

Run from the backend/ directory:

    pip install -r requirements.txt
    python -m pytest tests/test_missing_values.py -v
"""

import numpy as np
import pandas as pd
import pytest

from app.data_pipeline.cleaning.missing_values import (
    MissingValueResult,
    handle_missing_values,
)


def _mock_sales_df(rows):
    """Build a standardized product line-item DataFrame from a list of rows."""
    columns = [
        "transaction_date",
        "order_id",
        "product_id",
        "product_name",
        "quantity",
        "unit_price",
        "category",
    ]
    return pd.DataFrame(rows, columns=columns)


BASE_ROW = ["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99, "Tools"]


def test_no_missing_values_keeps_everything():
    df = _mock_sales_df([BASE_ROW, list(BASE_ROW)])
    result = handle_missing_values(df)

    assert isinstance(result, MissingValueResult)
    assert result.rows_excluded == 0
    assert result.values_filled == 0
    assert result.rows_kept == 2


# (field name, its column index in BASE_ROW) for every critical field.
CRITICAL_FIELD_INDEX = {
    "transaction_date": 0,
    "product_id": 2,
    "quantity": 4,
    "unit_price": 5,
}


@pytest.mark.parametrize("field,idx", list(CRITICAL_FIELD_INDEX.items()))
def test_each_missing_critical_field_excludes_row(field, idx):
    bad = list(BASE_ROW)
    bad[idx] = np.nan  # missing one critical field
    df = _mock_sales_df([BASE_ROW, bad])
    result = handle_missing_values(df)

    assert result.rows_excluded == 1, f"missing {field} should exclude the row"
    assert result.rows_kept == 1


def test_missing_optional_field_is_filled():
    row = list(BASE_ROW)
    row[6] = np.nan  # missing category (optional)
    df = _mock_sales_df([row])
    result = handle_missing_values(df)

    assert result.values_filled == 1
    assert result.rows_excluded == 0
    assert result.dataframe.loc[0, "category"] == "Uncategorized"


def test_missing_product_name_filled_with_unknown():
    row = list(BASE_ROW)
    row[3] = np.nan  # missing product_name (optional)
    df = _mock_sales_df([row])
    result = handle_missing_values(df)

    assert result.dataframe.loc[0, "product_name"] == "Unknown"


def test_empty_and_whitespace_treated_as_missing():
    row1 = list(BASE_ROW)
    row1[6] = ""  # empty string category -> filled
    row2 = list(BASE_ROW)
    row2[6] = "   "  # whitespace category -> filled
    df = _mock_sales_df([row1, row2])
    result = handle_missing_values(df)

    assert result.values_filled == 2
    assert (result.dataframe["category"] == "Uncategorized").all()


def test_placeholder_strings_treated_as_missing():
    row = list(BASE_ROW)
    row[0] = "N/A"  # placeholder in critical transaction_date -> row excluded
    df = _mock_sales_df([row])
    result = handle_missing_values(df)

    assert result.rows_excluded == 1
    assert result.rows_kept == 0


def test_missing_order_id_is_kept_and_flagged():
    bad = list(BASE_ROW)
    bad[1] = np.nan  # missing order_id -> kept, not excluded
    df = _mock_sales_df([BASE_ROW, bad])
    result = handle_missing_values(df)

    assert result.rows_excluded == 0
    assert result.rows_kept == 2
    assert result.flagged_missing["order_id"] == 1


def test_order_id_placeholder_flagged_and_not_filled():
    row = list(BASE_ROW)
    row[1] = "N/A"  # placeholder order_id -> normalized to NaN, kept, flagged
    df = _mock_sales_df([row])
    result = handle_missing_values(df)

    assert result.rows_kept == 1
    assert result.flagged_missing["order_id"] == 1
    assert pd.isna(result.dataframe.loc[0, "order_id"])  # left blank, not filled


def test_row_missing_both_critical_and_optional():
    row = list(BASE_ROW)
    row[4] = np.nan  # missing quantity (critical) -> excluded
    row[6] = np.nan  # missing category (optional)
    df = _mock_sales_df([row])
    result = handle_missing_values(df)

    # Row is excluded for the critical field; no fill is counted for a dropped row's
    # optional gap because filling happens first, but the row still leaves the set.
    assert result.rows_excluded == 1
    assert result.rows_kept == 0


def test_all_rows_missing_critical_returns_empty():
    rows = []
    for _ in range(3):
        r = list(BASE_ROW)
        r[2] = np.nan  # missing product_id
        rows.append(r)
    df = _mock_sales_df(rows)
    result = handle_missing_values(df)

    assert result.rows_kept == 0
    assert result.rows_excluded == 3


def test_empty_dataframe():
    df = _mock_sales_df([])
    result = handle_missing_values(df)

    assert result.rows_checked == 0
    assert result.rows_kept == 0
    assert result.rows_excluded == 0
    assert result.values_filled == 0


def test_index_is_reset():
    bad = list(BASE_ROW)
    bad[0] = np.nan  # missing transaction_date -> excluded (row 1)
    df = _mock_sales_df([BASE_ROW, bad, list(BASE_ROW)])
    result = handle_missing_values(df)

    assert list(result.dataframe.index) == [0, 1]


def test_original_dataframe_not_mutated():
    row = list(BASE_ROW)
    row[6] = np.nan
    df = _mock_sales_df([row])
    handle_missing_values(df)

    # original still has the NaN, not the filled default
    assert pd.isna(df.loc[0, "category"])


def test_invalid_input_type_raises():
    with pytest.raises(TypeError):
        handle_missing_values([1, 2, 3])


def test_summary_message():
    row = list(BASE_ROW)
    row[6] = np.nan
    df = _mock_sales_df([row])
    result = handle_missing_values(df)
    assert "filled 1 value" in result.summary()
