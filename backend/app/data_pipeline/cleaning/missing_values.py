"""Missing-value handling for the standardized sales DataFrame.

Keeps analysis running by handling incomplete rows with predefined rules.
Fields fall into three groups:

- critical: a row missing any of these is excluded (it can't produce a valid KPI)
- optional: missing values are filled with a default so the row is kept
- flagged: kept as-is (never filled, never excludes the row), but counted so
  downstream KPIs and the data-quality summary can see the gap

Handles missing/empty values only (not invalid ones). See
docs/missing_value_handling.md for the full definition.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Rows missing any of these cannot produce a valid KPI, so the row is excluded.
CRITICAL_FIELDS = [
    "transaction_date",
    "product_id",
    "quantity",
    "unit_price",
]

# Missing values in these fields are filled with a default so the row is kept.
OPTIONAL_DEFAULTS = {
    "product_name": "Unknown",
    "category": "Uncategorized",
}

# Fields kept as-is when missing (never filled, never excluded) but counted.
# order_id is here because a line item with no order_id is still valid for
# revenue, product, and time-based KPIs; only order-level KPIs (order count,
# average order value) skip it, which they handle at calculation time. Filling it
# with a placeholder would merge blank rows into one fake order and corrupt those
# KPIs, so it is left blank and reported instead.
FLAGGED_FIELDS = ["order_id"]

# String values treated as missing (compared case-insensitively, after strip).
MISSING_PLACEHOLDERS = {"", "n/a", "na", "-", "null", "none"}


@dataclass
class MissingValueResult:
    """Outcome of a missing-value handling pass.

    Attributes:
        dataframe: the cleaned DataFrame.
        rows_checked: number of rows before handling.
        values_filled: number of optional-field values filled with a default.
        rows_excluded: number of rows removed for missing a critical field.
        rows_kept: number of rows remaining after handling.
        flagged_missing: for each flagged field, how many kept rows are missing
            it (e.g. {"order_id": 12}).
    """

    dataframe: pd.DataFrame
    rows_checked: int
    values_filled: int
    rows_excluded: int
    rows_kept: int
    flagged_missing: dict[str, int]

    def summary(self) -> str:
        """One-line summary, useful for logs and the UI."""
        flagged = ", ".join(f"{n} missing {field}" for field, n in self.flagged_missing.items() if n)
        flagged_part = f" ({flagged})" if flagged else ""
        return (
            f"Handled missing values: filled {self.values_filled} value(s), "
            f"excluded {self.rows_excluded} row(s), "
            f"kept {self.rows_kept} of {self.rows_checked}{flagged_part}."
        )


def _normalize_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy where empty/placeholder strings become real NaN.

    Text values are stripped of surrounding whitespace, and anything matching a
    known placeholder (case-insensitive) is converted to NaN so the rules below
    apply consistently.
    """

    def normalize(value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.lower() in MISSING_PLACEHOLDERS:
                return np.nan
            return stripped
        return value

    # Rebuild as a new DataFrame so we never write into the caller's frame.
    normalized = {col: (series.map(normalize) if series.dtype == object else series) for col, series in df.items()}
    return pd.DataFrame(normalized, index=df.index)


def handle_missing_values(
    df: pd.DataFrame,
    *,
    critical_fields: list[str] | None = None,
    optional_defaults: dict[str, object] | None = None,
    flagged_fields: list[str] | None = None,
) -> MissingValueResult:
    """Handle missing values on a standardized DataFrame.

    Optional-field gaps are filled with a default; rows missing any critical
    field are excluded; flagged fields are kept as-is but counted. The input is
    not modified and the index is reset so downstream pipeline steps get a clean
    0..n-1 range.

    Args:
        df: the (already standardized) input DataFrame.
        critical_fields: fields that force row exclusion when missing.
            Defaults to CRITICAL_FIELDS.
        optional_defaults: mapping of optional field -> default fill value.
            Defaults to OPTIONAL_DEFAULTS.
        flagged_fields: fields kept as-is when missing but counted.
            Defaults to FLAGGED_FIELDS.

    Returns:
        A MissingValueResult with the cleaned DataFrame and counts.

    Raises:
        TypeError: if ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    critical_fields = CRITICAL_FIELDS if critical_fields is None else critical_fields
    optional_defaults = OPTIONAL_DEFAULTS if optional_defaults is None else optional_defaults
    flagged_fields = FLAGGED_FIELDS if flagged_fields is None else flagged_fields

    rows_checked = len(df)
    working = _normalize_missing(df)

    optional_present = {col: default for col, default in optional_defaults.items() if col in working.columns}
    values_filled = int(working[list(optional_present)].isna().sum().sum()) if optional_present else 0
    if optional_present:
        working = pd.DataFrame(
            {
                col: (series.fillna(optional_present[col]) if col in optional_present else series)
                for col, series in working.items()
            },
            index=working.index,
        )

    # Exclude rows missing any critical field that is actually present.
    present_critical = [c for c in critical_fields if c in working.columns]
    if present_critical:
        missing_mask = working[present_critical].isna().any(axis=1)
        rows_excluded = int(missing_mask.sum())
        working = working[~missing_mask]
    else:
        rows_excluded = 0

    working = working.reset_index(drop=True)

    # Count flagged fields still missing in the kept rows (kept, not excluded).
    flagged_missing = {col: int(working[col].isna().sum()) for col in flagged_fields if col in working.columns}

    return MissingValueResult(
        dataframe=working,
        rows_checked=rows_checked,
        values_filled=values_filled,
        rows_excluded=rows_excluded,
        rows_kept=len(working),
        flagged_missing=flagged_missing,
    )
