"""Tests for the single cleaning step run while an upload is prepared.

Run from the backend/ directory:

    pip install -r requirements.txt
    python -m pytest tests/test_cleaning.py -v
"""

import pandas as pd
import pytest

from app.data_pipeline.cleaning.service import CleaningResult, clean_dataframe
from app.data_pipeline.standardize import coerce_field_types

COLUMNS = [
    "transaction_date",
    "order_id",
    "product_id",
    "product_name",
    "quantity",
    "unit_price",
    "category",
]

BASE_ROW = ["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99, "Tools"]
OTHER_ROW = ["2026-01-16", "ORD-2", "P-200", "Gadget", 1, 19.99, "Tools"]


def _sales_df(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


def test_runs_both_steps_and_reports_each():
    df = _sales_df([BASE_ROW, list(BASE_ROW), OTHER_ROW])
    result = clean_dataframe(df)

    assert isinstance(result, CleaningResult)
    assert result.rows_read == 3
    assert result.rows_kept == 2
    assert result.duplicates.duplicates_removed == 1
    assert result.missing_values.rows_excluded == 0


def test_counts_reconcile():
    incomplete = ["2026-01-17", "ORD-3", "P-300", "Doohickey", None, 4.50, "Tools"]
    df = _sales_df([BASE_ROW, list(BASE_ROW), OTHER_ROW, incomplete])
    result = clean_dataframe(df)

    excluded = result.missing_values.rows_excluded
    removed = result.duplicates.duplicates_removed

    assert result.rows_read - excluded - removed == result.rows_kept


def test_rows_missing_a_critical_field_are_excluded():
    no_date = [None, "ORD-3", "P-300", "Doohickey", 5, 4.50, "Tools"]
    df = _sales_df([BASE_ROW, no_date])
    result = clean_dataframe(df)

    assert result.missing_values.rows_excluded == 1
    assert result.rows_kept == 1


def test_optional_gaps_are_filled_not_excluded():
    no_category = ["2026-01-16", "ORD-2", "P-200", "Gadget", 1, 19.99, None]
    df = _sales_df([BASE_ROW, no_category])
    result = clean_dataframe(df)

    assert result.missing_values.values_filled == 1
    assert result.rows_kept == 2
    assert result.dataframe["category"].iloc[1] == "Uncategorized"


def test_blank_order_id_is_flagged_but_kept():
    blank_order = ["2026-01-16", "", "P-200", "Gadget", 1, 19.99, "Tools"]
    df = _sales_df([BASE_ROW, blank_order])
    result = clean_dataframe(df)

    assert result.rows_kept == 2
    assert result.to_dict()["flagged_missing"]["order_id"] == 1


def test_missing_values_run_before_duplicates():
    """Two rows differing only in how an empty category was written.

    The missing-value step turns "" and "N/A" into the same filled default, so
    duplicate detection then sees one row twice. Running duplicate removal first
    would keep both, which is why the order in clean_dataframe is fixed.
    """
    written_blank = ["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99, ""]
    written_na = ["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99, "N/A"]
    result = clean_dataframe(_sales_df([written_blank, written_na]))

    assert result.duplicates.duplicates_removed == 1
    assert result.rows_kept == 1


def test_dates_in_different_formats_are_detected_as_duplicates():
    """The behaviour docs/deduplication.md describes.

    The same sale written with two date formats is one duplicate, but only once
    the dates have been converted. Without the conversion the two rows are just
    different strings.
    """
    slashes = ["01/02/2026", "ORD-1", "P-100", "Widget", 2, 9.99, "Tools"]
    dashes = ["2026-01-02", "ORD-1", "P-100", "Widget", 2, 9.99, "Tools"]
    raw = _sales_df([slashes, dashes])

    assert clean_dataframe(raw).duplicates.duplicates_removed == 0
    assert clean_dataframe(coerce_field_types(raw)).duplicates.duplicates_removed == 1


def test_summary_dict_shape():
    df = _sales_df([BASE_ROW, list(BASE_ROW), OTHER_ROW])
    summary = clean_dataframe(df).to_dict()

    assert summary == {
        "rows_read": 3,
        "rows_kept": 2,
        "values_filled": 0,
        "rows_excluded": 0,
        "duplicates_removed": 1,
        "flagged_missing": {"order_id": 0},
    }


def test_summary_line_mentions_both_steps():
    df = _sales_df([BASE_ROW, list(BASE_ROW)])
    summary = clean_dataframe(df).summary()

    assert "duplicate" in summary
    assert "excluded" in summary


def test_cleaned_frame_has_a_fresh_index():
    df = _sales_df([BASE_ROW, list(BASE_ROW), OTHER_ROW])
    result = clean_dataframe(df)

    assert list(result.dataframe.index) == list(range(len(result.dataframe)))


def test_empty_frame_is_handled():
    result = clean_dataframe(_sales_df([]))

    assert result.rows_read == 0
    assert result.rows_kept == 0


def test_rejects_a_non_dataframe():
    with pytest.raises(TypeError):
        clean_dataframe([1, 2, 3])
