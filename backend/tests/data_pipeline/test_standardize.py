"""Tests for standardising a parsed file into the internal line-item frame.

Run from the backend/ directory:

    pip install -r requirements.txt
    python -m pytest tests/test_standardize.py -v
"""

import pandas as pd
import pytest

from app.data_pipeline.standardize import (
    apply_column_mapping,
    coerce_field_types,
    mapped_fields_from_result,
    standardize_dataframe,
)

RAW_MAPPING = {
    "Order Date": "transaction_date",
    "Order No": "order_id",
    "SKU": "product_id",
    "Item": "product_name",
    "Qty": "quantity",
    "Unit Price": "unit_price",
}


def _raw_df(rows=None):
    """A parsed file using the uploader's own headers, plus a junk column."""
    rows = rows or [["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99, "ignore me"]]
    return pd.DataFrame(
        rows,
        columns=[
            "Order Date",
            "Order No",
            "SKU",
            "Item",
            "Qty",
            "Unit Price",
            "Notes",
        ],
    )


def test_renames_mapped_columns_to_standard_fields():
    result = apply_column_mapping(_raw_df(), RAW_MAPPING)

    assert list(result.columns) == [
        "transaction_date",
        "order_id",
        "product_id",
        "product_name",
        "quantity",
        "unit_price",
    ]


def test_drops_columns_the_mapping_does_not_cover():
    result = apply_column_mapping(_raw_df(), RAW_MAPPING)

    assert "Notes" not in result.columns


def test_preserves_row_order_and_count():
    rows = [
        ["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99, "x"],
        ["2026-01-16", "ORD-2", "P-200", "Gadget", 1, 19.99, "y"],
        ["2026-01-17", "ORD-3", "P-300", "Doohickey", 5, 4.50, "z"],
    ]
    result = apply_column_mapping(_raw_df(rows), RAW_MAPPING)

    assert len(result) == 3
    assert list(result["order_id"]) == ["ORD-1", "ORD-2", "ORD-3"]


def test_empty_mapping_keeps_the_rows_but_no_columns():
    result = apply_column_mapping(_raw_df(), {})

    assert list(result.columns) == []
    assert len(result) == 1


def test_does_not_modify_the_input_frame():
    df = _raw_df()
    apply_column_mapping(df, RAW_MAPPING)

    assert "Order Date" in df.columns


def test_rejects_a_non_dataframe():
    with pytest.raises(TypeError):
        apply_column_mapping([1, 2, 3], RAW_MAPPING)


def test_rejects_a_source_column_that_is_not_in_the_file():
    with pytest.raises(KeyError):
        apply_column_mapping(_raw_df(), {"Nope": "quantity"})


def test_rejects_two_columns_claiming_the_same_field():
    mapping = {"Qty": "quantity", "Unit Price": "quantity"}

    with pytest.raises(ValueError):
        apply_column_mapping(_raw_df(), mapping)


def test_mapped_fields_takes_only_recognised_columns():
    mapping_result = {
        "recognised": [
            {"column": "Qty", "suggested_field": "quantity", "confidence": 0.9},
        ],
        "ambiguous": [
            {"column": "Date", "suggested_field": "transaction_date", "confidence": 0.82},
        ],
        "unrecognised": [
            {"column": "Notes", "suggested_field": None, "confidence": 0.1},
        ],
    }

    assert mapped_fields_from_result(mapping_result) == {"Qty": "quantity"}


def test_mapped_fields_handles_an_empty_contract():
    assert mapped_fields_from_result({}) == {}


def test_dates_written_in_different_formats_become_one_type():
    df = pd.DataFrame({"transaction_date": ["01/02/2026", "2026-01-02"]})
    result = coerce_field_types(df)

    assert result["transaction_date"].iloc[0] == result["transaction_date"].iloc[1]


def test_unreadable_dates_become_missing_rather_than_raising():
    df = pd.DataFrame({"transaction_date": ["2026-01-15", "see note", ""]})
    result = coerce_field_types(df)

    assert result["transaction_date"].isna().sum() == 2


def test_numeric_fields_read_from_text():
    df = pd.DataFrame({"quantity": ["2", "3"], "unit_price": ["9.99", "1.50"]})
    result = coerce_field_types(df)

    assert list(result["quantity"]) == [2, 3]
    assert result["unit_price"].sum() == pytest.approx(11.49)


def test_unreadable_numbers_become_missing():
    df = pd.DataFrame({"quantity": [2, "N/A"], "unit_price": ["45.00 SAR", 1.5]})
    result = coerce_field_types(df)

    assert result["quantity"].isna().sum() == 1
    assert result["unit_price"].isna().sum() == 1


def test_text_fields_are_left_alone():
    df = pd.DataFrame({"product_id": [12345, "P-2"], "category": ["Tools", None]})
    result = coerce_field_types(df)

    assert result["product_id"].iloc[0] == 12345
    assert result["category"].iloc[0] == "Tools"


def test_coercion_ignores_fields_the_file_does_not_have():
    df = pd.DataFrame({"quantity": ["2"]})
    result = coerce_field_types(df)

    assert list(result.columns) == ["quantity"]


def test_standardize_renames_then_coerces():
    result = standardize_dataframe(_raw_df(), RAW_MAPPING)

    assert list(result.columns) == [
        "transaction_date",
        "order_id",
        "product_id",
        "product_name",
        "quantity",
        "unit_price",
    ]
    assert pd.api.types.is_datetime64_any_dtype(result["transaction_date"])
    assert pd.api.types.is_numeric_dtype(result["unit_price"])
