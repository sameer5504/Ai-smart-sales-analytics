from __future__ import annotations

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.data_pipeline.cleaning.service import CleaningResult, clean_dataframe
from app.data_pipeline.mapping.parser_bridge import extract_headers, map_parsed_file
from app.data_pipeline.parsing import parse_file
from app.data_pipeline.standardize import (
    coerce_field_types,
    mapped_fields_from_result,
    standardize_dataframe,
)
from app.data_pipeline.validation.required_fields import validate_required_fields
from app.storage.azure_storage import AzureStorage

logger = logging.getLogger(__name__)

# Revenue is worked out once here rather than in every feature that needs it.
QUANTITY_FIELD = "quantity"
PRICE_FIELD = "unit_price"
REVENUE_FIELD = "revenue"


class PreparationError(Exception):
    """Raised when an uploaded file cannot be turned into usable rows."""


@dataclass
class PreparedUpload:
    """Everything preparation produced for one uploaded file.

    Attributes:
        dataframe: the cleaned, standardised DataFrame.
        row_count: rows in the cleaned DataFrame.
        columns: the raw column headers read from the file, in file order.
            This is what a manual-mapping step shows the user when stored is
            False, so they can see exactly what needs mapping.
        mapping: the column-mapping contract, including anything ambiguous or
            unrecognised, for a manual-mapping step to act on.
        validation: the required-field validation result.
        cleaning: the cleaning result and its counts.
        stored: whether the required fields were successfully identified
            (i.e. this upload is usable). NOTE: this reflects validation
            success, not necessarily that anything was actually written to
            storage - see the `persist` parameter on prepare_upload. False
            when required fields could not be identified, because rows
            without them are not usable and should not reach anything
            downstream.
        content_hash: SHA-256 of the cleaned CSV bytes, or None if
            validation failed. Two uploads that hash the same have
            identical data AND mapping (a different mapping produces a
            differently-shaped CSV, so the hash changes too) - used to
            detect an exact-duplicate upload before saving it again (see
            /api/mapping/apply and datasets_repository.find_matching_dataset).
            Computed even when persist=False, so a caller can check for a
            duplicate before deciding whether to actually persist.
        stored_filename: the exact blob name the prepared rows were written
            under (unique per upload - see _unique_stored_name), or None if
            they were not actually persisted (either validation failed, or
            persist=False was requested). Callers that need to read this
            upload back (load_cleaned) must use this exact value, not the
            original display filename.
        cleaned_path: the "container/blob" reference the prepared rows were
            written to (see AzureStorage.save), or None if nothing was
            persisted. This is what gets persisted as datasets.blob_path.
    """

    dataframe: pd.DataFrame
    row_count: int
    columns: list[str]
    mapping: dict
    validation: dict
    cleaning: CleaningResult
    stored: bool
    content_hash: str | None
    stored_filename: str | None
    cleaned_path: str | None


def _display_filename(filename: str) -> str:
    """Return the human-facing name for an uploaded file (what the user
    sees in their file list) - unchanged across re-uploads of "the same"
    file name.
    """
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name:
        raise ValueError(f"Invalid filename: {filename!r}")
    return f"{Path(safe_name).stem}.csv"


def _unique_stored_name(filename: str) -> str:
    """Return a blob name that is unique to *this* upload.

    Re-uploading a file with the same display name (e.g. a different
    mapping or currency chosen the second time) must not overwrite the
    first upload's blob - each upload gets its own short random prefix, so
    "sales.csv" uploaded twice produces two distinct blobs, e.g.
    "a1b2c3d4_sales.csv" and "f9e8d7c6_sales.csv".
    """
    unique_id = uuid.uuid4().hex[:8]
    return f"{unique_id}_{_display_filename(filename)}"


def _content_hash(csv_bytes: bytes) -> str:
    return hashlib.sha256(csv_bytes).hexdigest()


def cleaned_filename_for(filename: str) -> str:
    """Public wrapper around _display_filename, for callers outside this
    module that need a dataset's display-facing cleaned name (e.g. showing
    it in a file list). This is NOT the name to load a specific upload
    back by - use the dataset row's stored blob name for that (see
    load_cleaned).
    """
    return _display_filename(filename)


def _add_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Add revenue per line item, so nothing downstream recomputes it.

    Skipped when either input field is absent, which happens when the column
    mapping could not identify them.
    """
    if QUANTITY_FIELD not in df.columns or PRICE_FIELD not in df.columns:
        return df

    with_revenue = df.copy()
    with_revenue[REVENUE_FIELD] = with_revenue[QUANTITY_FIELD] * with_revenue[PRICE_FIELD]
    return with_revenue


async def prepare_upload(
    file_path: str,
    data_type: str,
    user_id: int,
    mapped_fields: dict[str, str] | None = None,
    persist: bool = True,
) -> PreparedUpload:
    """Parse, map, validate, standardise and clean an uploaded file.

    Rows are only usable when the required fields were identified. A file whose
    date or price column could not be recognised produces a result that reports
    the problem rather than a set of rows missing half their fields.

    Args:
        file_path: path to the saved upload (the raw file, still handled by
            the shared local scratch storage - see upload/service.py).
        data_type: the data type the user selected, e.g. "sales".
        user_id: the authenticated user this upload belongs to. When
            persisted, the cleaned result is written only to this user's
            folder in the shared datasets container.
        mapped_fields: ``{source_column: standard_field}`` to use instead of the
            automatic match. This is how a manual mapping step feeds a
            user-confirmed mapping in; when it is None the confident automatic
            matches are used.
        persist: whether to actually write the cleaned result to storage.
            False is used for a preview (see /api/upload, and the
            duplicate-check step in /api/mapping/apply) that only needs
            validation/columns/data-quality/content_hash back, without
            saving anything - the confirm step always persists. Defaults
            to True for any other/direct caller.

    Returns:
        A PreparedUpload holding the cleaned data and everything learned on the
        way to it.

    Raises:
        PreparationError: if the file cannot be read, or holds no rows.
    """
    name = Path(file_path).name

    try:
        parsed = parse_file(file_path)
    except Exception as exc:
        # pandas raises a range of types for a malformed file, and the caller
        # only needs to know that this upload could not be read.
        logger.warning("Could not parse %s: %s", name, exc)
        raise PreparationError(f"Could not read {name}: {exc}") from exc

    dataframe = parsed["dataframe"]

    if dataframe.empty:
        logger.warning("Upload %s has no data rows", name)
        raise PreparationError(f"{name} has column headings but no data rows.")

    columns = extract_headers(dataframe)
    mapping = map_parsed_file(dataframe)

    if mapped_fields is None:
        mapped_fields = mapped_fields_from_result(mapping)

    # Required-field validation has to run against whichever mapping is
    # actually being applied. A manual mapping step's whole point is to
    # supply fields the automatic matcher missed, so checking the
    # automatic mapping here (as this used to do) would report a file as
    # incomplete even after the caller fixed exactly that problem.
    validation = validate_required_fields({"data_type": data_type, "mapped_fields": mapped_fields})

    standardized = standardize_dataframe(dataframe, mapped_fields)
    cleaning = clean_dataframe(standardized)
    prepared = _add_revenue(cleaning.dataframe)

    if not validation["is_valid"]:
        logger.warning(
            "Upload %s is missing required fields after mapping: %s",
            name,
            ", ".join(validation["missing_required_fields"]),
        )
        return PreparedUpload(
            dataframe=prepared,
            row_count=0,
            columns=columns,
            mapping=mapping,
            validation=validation,
            cleaning=cleaning,
            stored=False,
            content_hash=None,
            stored_filename=None,
            cleaned_path=None,
        )

    csv_bytes = prepared.to_csv(index=False).encode("utf-8")
    content_hash = _content_hash(csv_bytes)

    if not persist:
        # Validation succeeded and the content hash is ready, but this call
        # is a preview/check only - nothing is written to Azure or
        # registered in the datasets table here.
        return PreparedUpload(
            dataframe=prepared,
            row_count=len(prepared),
            columns=columns,
            mapping=mapping,
            validation=validation,
            cleaning=cleaning,
            stored=True,
            content_hash=content_hash,
            stored_filename=None,
            cleaned_path=None,
        )

    storage = AzureStorage(user_id=user_id)
    stored_filename = _unique_stored_name(name)
    cleaned_path = await storage.save(stored_filename, csv_bytes)

    logger.info(
        "Prepared %s for user %s: read %d, kept %d, excluded %d, duplicates %d, filled %d",
        name,
        user_id,
        cleaning.rows_read,
        cleaning.rows_kept,
        cleaning.missing_values.rows_excluded,
        cleaning.duplicates.duplicates_removed,
        cleaning.missing_values.values_filled,
    )

    return PreparedUpload(
        dataframe=prepared,
        row_count=len(prepared),
        columns=columns,
        mapping=mapping,
        validation=validation,
        cleaning=cleaning,
        stored=True,
        content_hash=content_hash,
        stored_filename=stored_filename,
        cleaned_path=cleaned_path,
    )


def load_cleaned(user_id: int, stored_filename: str) -> pd.DataFrame:
    """Return the prepared rows for a previously uploaded file, scoped to
    one user.

    This is the read side of the pipeline. Features that need a business's
    sales data should call this instead of parsing the upload again, so they
    all work from the same rows - and so they can never read another user's
    data, since the lookup only ever touches ``user_id``'s own folder.

    Args:
        user_id: the authenticated user whose data is being read. Must come
            from the authenticated request (e.g. current_user["user_id"]),
            never from a value supplied by the client.
        stored_filename: the EXACT blob name this upload was stored under
            (dataset row's stored name - see PreparedUpload.stored_filename),
            not the display filename shown to the user. A display filename
            like "sales.csv" can have several uploads behind it, each with
            its own unique stored_filename.

    Returns:
        The prepared DataFrame, with its typed fields restored.

    Raises:
        ValueError: if stored_filename is not a plain filename.
        FileNotFoundError: if this user has no prepared data under that
            stored name.
    """
    storage = AzureStorage(user_id=user_id)

    try:
        contents = storage.load(stored_filename)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"No prepared data for '{stored_filename}'") from exc

    # CSV has no types of its own, so the typed fields are restored on the way
    # back out rather than handed to callers as strings.
    return coerce_field_types(pd.read_csv(io.BytesIO(contents)))
