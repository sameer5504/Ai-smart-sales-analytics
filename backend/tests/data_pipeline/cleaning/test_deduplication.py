"""Tests for exact duplicate removal.

Run from the backend/ directory:

    pip install -r requirements.txt
    python -m pytest tests/test_deduplication.py -v
"""

import numpy as np
import pandas as pd
import pytest

from app.data_pipeline.cleaning.deduplication import (
    DeduplicationResult,
    remove_exact_duplicates,
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
OTHER_ROW = ["2026-01-16", "ORD-2", "P-200", "Gadget", 1, 19.99, "Tools"]


def test_removes_exact_duplicate():
    df = _mock_sales_df([BASE_ROW, list(BASE_ROW), OTHER_ROW])
    result = remove_exact_duplicates(df)

    assert isinstance(result, DeduplicationResult)
    assert result.rows_before == 3
    assert result.rows_after == 2
    assert result.duplicates_removed == 1


def test_keeps_rows_with_no_duplicates():
    df = _mock_sales_df([BASE_ROW, OTHER_ROW])
    result = remove_exact_duplicates(df)

    assert result.duplicates_removed == 0
    assert result.rows_after == 2


def test_all_rows_identical_collapse_to_one():
    df = _mock_sales_df([list(BASE_ROW) for _ in range(5)])
    result = remove_exact_duplicates(df)

    assert result.rows_after == 1
    assert result.duplicates_removed == 4


def test_rows_differing_in_one_field_are_not_duplicates():
    # Same order + product but different quantity = legitimate separate line item.
    row_a = list(BASE_ROW)
    row_b = list(BASE_ROW)
    row_b[4] = 3  # quantity 2 -> 3
    df = _mock_sales_df([row_a, row_b])
    result = remove_exact_duplicates(df)

    assert result.duplicates_removed == 0
    assert result.rows_after == 2


def test_nan_values_treated_as_equal():
    row_a = list(BASE_ROW)
    row_a[6] = np.nan  # empty category
    row_b = list(row_a)  # identical, also NaN category
    df = _mock_sales_df([row_a, row_b])
    result = remove_exact_duplicates(df)

    assert result.duplicates_removed == 1
    assert result.rows_after == 1


def test_empty_dataframe():
    df = _mock_sales_df([])
    result = remove_exact_duplicates(df)

    assert result.rows_before == 0
    assert result.rows_after == 0
    assert result.duplicates_removed == 0


def test_index_is_reset():
    df = _mock_sales_df([BASE_ROW, list(BASE_ROW), OTHER_ROW])
    result = remove_exact_duplicates(df)

    assert list(result.dataframe.index) == [0, 1]


def test_original_dataframe_not_mutated():
    df = _mock_sales_df([BASE_ROW, list(BASE_ROW)])
    remove_exact_duplicates(df)

    assert len(df) == 2  # untouched


def test_subset_deduplication():
    row_a = list(BASE_ROW)
    row_b = list(BASE_ROW)
    row_b[5] = 12.50  # different unit_price
    df = _mock_sales_df([row_a, row_b])

    # By default these are NOT duplicates (price differs)...
    assert remove_exact_duplicates(df).duplicates_removed == 0
    # ...but on the order_id + product_id key they are.
    result = remove_exact_duplicates(df, subset=["order_id", "product_id"])
    assert result.duplicates_removed == 1


def test_invalid_input_type_raises():
    with pytest.raises(TypeError):
        remove_exact_duplicates([1, 2, 3])


def test_invalid_subset_column_raises():
    df = _mock_sales_df([BASE_ROW])
    with pytest.raises(KeyError):
        remove_exact_duplicates(df, subset=["does_not_exist"])


def test_summary_message():
    df = _mock_sales_df([BASE_ROW, list(BASE_ROW)])
    result = remove_exact_duplicates(df)
    assert "Removed 1 duplicate" in result.summary()
