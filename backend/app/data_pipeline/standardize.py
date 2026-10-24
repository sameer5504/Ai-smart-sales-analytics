"""Standardisation of a parsed sales file into the internal line-item frame.

Column mapping decides which uploaded column means which standard field. This
module applies that decision to the data: it renames the mapped columns, drops
the rest, and converts the typed fields. After it runs, a row is one product per
order under the standard field names, which is the shape the cleaning rules in
this package are written against.

The type conversion is what lets duplicate detection work as documented. Without
it, two identical sales written as "01/02/2026" and "2026-02-01" compare as
different strings and the duplicate is missed.
"""

from __future__ import annotations

import pandas as pd

# Standard fields that carry a type other than free text. Text fields are left
# alone on purpose: handle_missing_values already strips and normalises object
# columns, and forcing a string conversion here would turn a product_id that
# Excel read as 12345 into "12345.0".
DATE_FIELDS = ["transaction_date"]
NUMERIC_FIELDS = ["quantity", "unit_price"]


def mapped_fields_from_result(mapping_result: dict) -> dict[str, str]:
    """Return ``{source_column: standard_field}`` for confidently matched columns.

    Reads the ``recognised`` group of a mapping contract, which the matcher fills
    with matches at or above its AUTO_ACCEPT confidence. Ambiguous and
    unrecognised columns are deliberately left out: acting on a low-confidence
    guess would file the wrong data under a standard field name, which is worse
    than dropping the column and reporting it.

    A manual mapping step can build the same dict from a user's choices and pass
    it to ``apply_column_mapping`` directly.

    Args:
        mapping_result: the contract returned by ``build_mapping_result``.

    Returns:
        A mapping of uploaded column name to standard field name.
    """
    return {
        item["column"]: item["suggested_field"]
        for item in mapping_result.get("recognised", [])
        if item.get("suggested_field")
    }


def apply_column_mapping(
    df: pd.DataFrame,
    mapped_fields: dict[str, str],
) -> pd.DataFrame:
    """Rename the mapped columns to standard field names and drop the rest.

    Columns the mapping does not cover are removed rather than carried along,
    so everything downstream can assume every column it sees is a standard
    field. Row order and the relative order of the kept columns are preserved.

    Args:
        df: the parsed DataFrame, still using the file's own headers.
        mapped_fields: ``{source_column: standard_field}``. The direction matches
            ``DataFrame.rename``. Note a manual-mapping step may hold this the
            other way round and need to invert it first.

    Returns:
        A new DataFrame containing only the mapped columns, renamed.

    Raises:
        TypeError: if ``df`` is not a pandas DataFrame.
        KeyError: if a source column is not in the DataFrame.
        ValueError: if two source columns claim the same standard field.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    missing = [column for column in mapped_fields if column not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")

    claimed: dict[str, str] = {}
    for column, field in mapped_fields.items():
        if field in claimed:
            raise ValueError(f"Standard field '{field}' is claimed by both '{claimed[field]}' and '{column}'")
        claimed[field] = column

    kept = [column for column in df.columns if column in mapped_fields]

    return df[kept].rename(columns=mapped_fields).copy()


def coerce_field_types(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the typed standard fields to the types the schema declares.

    Dates are parsed per value rather than by inferring one format for the whole
    column, so a file that mixes formats is read correctly instead of losing
    every row that does not match the first one. Values that cannot be converted
    become NaT or NaN, which the missing-value rules already treat as missing, so
    an unreadable price excludes its row through the existing critical-field rule
    rather than needing separate handling here.

    ``unit_price`` becomes a float rather than the Decimal declared in
    SalesRecordSchema, because pandas does not handle Decimal columns well.

    Args:
        df: a DataFrame whose columns are already standard field names.

    Returns:
        A new DataFrame with the typed fields converted. Other columns and the
        index are passed through untouched.

    Raises:
        TypeError: if ``df`` is not a pandas DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected a pandas DataFrame, got {type(df).__name__}")

    converted = {}
    for column, series in df.items():
        if column in DATE_FIELDS:
            converted[column] = pd.to_datetime(series, errors="coerce", format="mixed")
        elif column in NUMERIC_FIELDS:
            converted[column] = pd.to_numeric(series, errors="coerce")
        else:
            converted[column] = series

    return pd.DataFrame(converted, index=df.index)


def standardize_dataframe(
    df: pd.DataFrame,
    mapped_fields: dict[str, str],
) -> pd.DataFrame:
    """Apply the mapping and then the type conversion.

    The order matters: the columns have to carry standard names before we can
    tell which one holds a date and which holds a number.

    Args:
        df: the parsed DataFrame, using the file's own headers.
        mapped_fields: ``{source_column: standard_field}``.

    Returns:
        The standardised DataFrame, ready for cleaning.
    """
    return coerce_field_types(apply_column_mapping(df, mapped_fields))
