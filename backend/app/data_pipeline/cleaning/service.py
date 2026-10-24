"""The single cleaning step, run once while an upload is being prepared.

Missing-value handling and duplicate removal exist as separate rules with their
own documents. This module is the one place that runs them, in the one order
they are meant to run in, and collects their counts into the data-quality
summary the business owner sees after an upload.

Everything downstream (KPIs, dashboards, forecasting) reads what comes out of
here, so no individual feature needs a cleaning pass of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.data_pipeline.cleaning.deduplication import DeduplicationResult, remove_exact_duplicates
from app.data_pipeline.cleaning.missing_values import MissingValueResult, handle_missing_values


@dataclass
class CleaningResult:
    """Outcome of a full cleaning pass.

    Attributes:
        dataframe: the cleaned DataFrame, ready to store and analyse.
        missing_values: the missing-value step's own result and counts.
        duplicates: the duplicate-removal step's own result and counts.
    """

    dataframe: pd.DataFrame
    missing_values: MissingValueResult
    duplicates: DeduplicationResult

    @property
    def rows_read(self) -> int:
        """Rows in the file before any cleaning."""
        return self.missing_values.rows_checked

    @property
    def rows_kept(self) -> int:
        """Rows left after both steps.

        Not the same as ``missing_values.rows_kept``, which is the count part
        way through, before duplicates have been removed.
        """
        return self.duplicates.rows_after

    def summary(self) -> str:
        """One-line summary, useful for logs."""
        return (
            f"Cleaned {self.rows_read} row(s) down to {self.rows_kept}: "
            f"filled {self.missing_values.values_filled} value(s), "
            f"excluded {self.missing_values.rows_excluded} incomplete row(s), "
            f"removed {self.duplicates.duplicates_removed} duplicate row(s)."
        )

    def to_dict(self) -> dict:
        """The data-quality summary, as sent to the client.

        Keys are flat because every number here comes straight from one of the
        two steps. A per-reason breakdown can be added later without changing
        any of these.
        """
        return {
            "rows_read": self.rows_read,
            "rows_kept": self.rows_kept,
            "values_filled": self.missing_values.values_filled,
            "rows_excluded": self.missing_values.rows_excluded,
            "duplicates_removed": self.duplicates.duplicates_removed,
            "flagged_missing": self.missing_values.flagged_missing,
        }


def clean_dataframe(df: pd.DataFrame) -> CleaningResult:
    """Run the full cleaning pass on a standardised DataFrame.

    Missing values are handled first and duplicates second. The order is not
    interchangeable: the missing-value step turns "", "N/A", "-" and friends
    into real blanks and fills the optional defaults, so by the time duplicate
    detection runs it is comparing values that have been made consistent. Two
    otherwise identical rows whose category was left empty in one and written
    "N/A" in the other are then correctly seen as the same row. Running
    duplicate removal first would keep both.

    Args:
        df: a standardised DataFrame, i.e. one whose columns are standard field
            names and whose typed fields have been converted.

    Returns:
        A CleaningResult with the cleaned DataFrame and the counts behind it.

    Raises:
        TypeError: if ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    missing_values = handle_missing_values(df)
    duplicates = remove_exact_duplicates(missing_values.dataframe)

    return CleaningResult(
        dataframe=duplicates.dataframe,
        missing_values=missing_values,
        duplicates=duplicates,
    )
