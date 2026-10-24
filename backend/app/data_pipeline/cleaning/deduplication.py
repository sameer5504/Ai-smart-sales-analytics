"""Exact duplicate removal for the standardized sales DataFrame.

An *exact duplicate* is a row whose values are identical to an earlier row
across every column. The first occurrence is kept; later identical rows are
removed. See docs/deduplication.md for the full definition.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class DeduplicationResult:
    """Outcome of a deduplication pass.

    Attributes:
        dataframe: the cleaned DataFrame with duplicate rows removed.
        rows_before: number of rows before deduplication.
        rows_after: number of rows kept after deduplication.
        duplicates_removed: number of rows removed (detected duplicates).
    """

    dataframe: pd.DataFrame
    rows_before: int
    rows_after: int
    duplicates_removed: int

    def summary(self) -> str:
        """Human-readable one-line summary, useful for logs and the UI."""
        return f"Removed {self.duplicates_removed} duplicate row(s): {self.rows_before} -> {self.rows_after}"


def remove_exact_duplicates(
    df: pd.DataFrame,
    *,
    subset: list[str] | None = None,
) -> DeduplicationResult:
    """Remove exact duplicate rows from a DataFrame.

    By default a row is a duplicate only when *all* columns match another row.
    NaN values are treated as equal to each other, so two otherwise-identical
    rows with an empty field are still duplicates. The first occurrence of each
    duplicate is kept and the index is reset so downstream pipeline steps get a
    clean 0..n-1 range.

    Args:
        df: the (already standardized) input DataFrame.
        subset: optional list of columns to compare on. Defaults to None,
            meaning all columns are used (the exact-duplicate rule). Pass a
            subset only if key-based deduplication is needed.

    Returns:
        A DeduplicationResult with the cleaned DataFrame and counts.

    Raises:
        TypeError: if ``df`` is not a pandas DataFrame.
        KeyError: if any column in ``subset`` is not in the DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    if subset is not None:
        missing = [col for col in subset if col not in df.columns]
        if missing:
            raise KeyError(f"Columns not found in DataFrame: {missing}")

    rows_before = len(df)

    cleaned = df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)

    rows_after = len(cleaned)

    return DeduplicationResult(
        dataframe=cleaned,
        rows_before=rows_before,
        rows_after=rows_after,
        duplicates_removed=rows_before - rows_after,
    )
