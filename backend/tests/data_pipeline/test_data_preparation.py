"""Tests for preparing an uploaded file for analysis.
Note: these tests call prepare_upload/load_cleaned directly (not through the
authenticated API), so a fixed TEST_USER_ID is used everywhere a cleaned file
is written and then read back. AzureStorage is mocked with an in-memory fake
(see _mock_azure_storage below) rather than hitting a real Azure Blob
container - the CI agent has no Azure credentials, and there's nothing
Azure-specific being tested here that a real container would exercise that
the fake doesn't already cover (save/exists/load round-tripping).

Each upload gets a unique stored filename now (see preparation.py's
_unique_stored_name), so re-uploading the same display name never overwrites
a previous upload. Tests that need to load a file back use
result.stored_filename rather than a hardcoded name.
"""

import os

import pandas as pd
import pytest

import app.data_pipeline.preparation as preparation
from app.data_pipeline.preparation import PreparationError, load_cleaned, prepare_upload

TEST_USER_ID = 999001

HEADERS = [
    "Order Date",
    "Order No",
    "SKU",
    "Item",
    "Qty",
    "Unit Price",
    "Product Category",
    "Notes",
]

# One base sale, the same sale entered twice more (once with the date written
# the other way round), a sale with no category, a sale whose price cannot be
# read, and a sale with no date at all.
MESSY_ROWS = [
    ["2026-01-15", "ORD-1", "P-100", "Widget", "2", "9.99", "Tools", "first"],
    ["2026-01-15", "ORD-1", "P-100", "Widget", "2", "9.99", "Tools", "second"],
    ["01/15/2026", "ORD-1", "P-100", "Widget", "2", "9.99", "Tools", "third"],
    ["2026-01-16", "ORD-2", "P-200", "Gadget", "1", "19.99", "", "fourth"],
    ["2026-01-17", "ORD-3", "P-300", "Doohickey", "5", "N/A", "Tools", "fifth"],
    ["", "ORD-4", "P-400", "Thing", "1", "4.50", "Tools", "sixth"],
]


def _write_messy_csv(directory, name="sales.csv", rows=None):
    path = directory / name
    frame = pd.DataFrame(rows if rows is not None else MESSY_ROWS, columns=HEADERS)
    frame.to_csv(path, index=False)
    return str(path)


def _safe_name(filename: str) -> str:
    """Mirrors AzureStorage's own _safe_blob_name check, so this fake
    raises the same ValueError a real Blob-backed call would for a path
    traversal attempt (e.g. "../../etc/passwd"), instead of silently
    treating it as a normal (if unusual) key.
    """
    safe = os.path.basename(filename)
    if safe != filename or not safe:
        raise ValueError(f"Invalid filename: {filename!r}")
    return safe


class _FakeAzureStorage:
    """In-memory stand-in for AzureStorage - the CI agent has no Azure
    credentials, so prepare_upload/load_cleaned need something other than a
    real Blob container to write to and read from. Shared dict is keyed by
    (user_id, filename), mirroring one container per user.
    """

    _store: dict = {}

    def __init__(self, user_id):
        self.user_id = user_id

    async def save(self, filename, contents):
        safe = _safe_name(filename)
        self._store[(self.user_id, safe)] = contents
        return f"user-{self.user_id}/{safe}"

    def exists(self, filename):
        safe = _safe_name(filename)
        return (self.user_id, safe) in self._store

    def load(self, filename):
        safe = _safe_name(filename)
        try:
            return self._store[(self.user_id, safe)]
        except KeyError as exc:
            raise FileNotFoundError(filename) from exc

    def delete(self, filename):
        safe = _safe_name(filename)
        self._store.pop((self.user_id, safe), None)

    def list_files(self):
        return [f for (uid, f) in self._store if uid == self.user_id]


@pytest.fixture(autouse=True)
def _mock_azure_storage(monkeypatch):
    _FakeAzureStorage._store.clear()
    # Patching it on the preparation module means prepare_upload/load_cleaned
    # (which resolve AzureStorage from their own module's globals at call
    # time) and this test file's own `preparation.AzureStorage(...)` calls
    # below both see the same fake, in sync with each other.
    monkeypatch.setattr(preparation, "AzureStorage", _FakeAzureStorage)


async def test_cleans_an_uploaded_file_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)

    assert result.cleaning.rows_read == 6
    assert result.cleaning.missing_values.rows_excluded == 2
    assert result.cleaning.duplicates.duplicates_removed == 2
    assert result.row_count == 2


async def test_cleaned_frame_uses_standard_field_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)

    assert "transaction_date" in result.dataframe.columns
    assert "Order Date" not in result.dataframe.columns
    assert "Notes" not in result.dataframe.columns


async def test_typed_fields_are_converted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)

    assert pd.api.types.is_datetime64_any_dtype(result.dataframe["transaction_date"])
    assert pd.api.types.is_numeric_dtype(result.dataframe["unit_price"])


async def test_writes_the_cleaned_dataset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)

    # Cleaned files are stored per-user under a unique name now (see
    # preparation._unique_stored_name), so re-uploading "sales.csv" never
    # overwrites a previous upload - only the display name is predictable,
    # the stored blob name carries a random per-upload prefix.
    assert result.stored_filename.endswith("_sales.csv")
    assert result.cleaned_path == f"user-{TEST_USER_ID}/{result.stored_filename}"
    assert preparation.AzureStorage(user_id=TEST_USER_ID).exists(result.stored_filename)


async def test_load_cleaned_returns_what_preparation_stored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)
    reloaded = load_cleaned(TEST_USER_ID, result.stored_filename)

    assert len(reloaded) == result.row_count
    assert list(reloaded.columns) == list(result.dataframe.columns)
    assert pd.api.types.is_datetime64_any_dtype(reloaded["transaction_date"])


async def test_carries_the_required_field_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)

    assert result.validation["is_valid"] is True
    assert result.validation["missing_required_fields"] == []


async def test_a_confirmed_mapping_overrides_the_automatic_one(tmp_path, monkeypatch):
    """The seam a manual mapping step plugs into.

    Passing mapped_fields means the automatic match is not consulted, so a
    user's correction wins.
    """
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(
        path,
        "sales",
        user_id=TEST_USER_ID,
        mapped_fields={"Order Date": "transaction_date", "Qty": "quantity"},
    )

    assert "transaction_date" in result.dataframe.columns
    assert "quantity" in result.dataframe.columns
    assert "product_name" not in result.dataframe.columns


async def test_revenue_is_worked_out_once(tmp_path, monkeypatch):
    """So no feature downstream has to multiply the two fields itself."""
    monkeypatch.chdir(tmp_path)
    path = _write_messy_csv(tmp_path)

    result = await prepare_upload(path, "sales", user_id=TEST_USER_ID)
    row = result.dataframe.iloc[0]

    assert "revenue" in result.dataframe.columns
    assert row["revenue"] == row["quantity"] * row["unit_price"]


async def test_unmappable_file_is_reported_and_not_stored(tmp_path, monkeypatch):
    """A file whose required columns were not recognised is not usable.

    Storing it would put rows with no date and no price where the dashboard and
    the forecast read, while the summary reported them as ready to use.
    """
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "mystery.csv"
    pd.DataFrame(
        [["2026-01-15", "ORD-1", "P-100", "Widget", 2, 9.99]],
        columns=[
            "Date of Sale",
            "Reference",
            "Stock Ref",
            "Description",
            "Units",
            "Value",
        ],
    ).to_csv(path, index=False)

    result = await prepare_upload(str(path), "sales", user_id=TEST_USER_ID)

    assert result.validation["is_valid"] is False
    assert "transaction_date" in result.validation["missing_required_fields"]
    assert result.stored is False
    assert result.row_count == 0
    assert result.stored_filename is None
    assert result.cleaned_path is None
    assert not preparation.AzureStorage(user_id=TEST_USER_ID).exists("mystery.csv")


async def test_a_file_with_headings_but_no_rows_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "headings.csv"
    path.write_text("Order Date,Order No,SKU,Item,Qty,Unit Price\n")

    with pytest.raises(PreparationError, match="no data rows"):
        await prepare_upload(str(path), "sales", user_id=TEST_USER_ID)


async def test_load_cleaned_has_nothing_for_an_unmappable_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "mystery.csv"
    pd.DataFrame([[1, 2, 3]], columns=["Col1", "Col2", "Col3"]).to_csv(path, index=False)

    await prepare_upload(str(path), "sales", user_id=TEST_USER_ID)

    with pytest.raises(FileNotFoundError):
        load_cleaned(TEST_USER_ID, "mystery.csv")


async def test_unreadable_file_raises_preparation_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "notes.txt"
    path.write_text("this is not a spreadsheet")

    with pytest.raises(PreparationError):
        await prepare_upload(str(path), "sales", user_id=TEST_USER_ID)


def test_load_cleaned_reports_a_file_that_was_never_prepared(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        load_cleaned(TEST_USER_ID, "never_uploaded.csv")


def test_load_cleaned_rejects_a_path_instead_of_a_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError):
        load_cleaned(TEST_USER_ID, "../../etc/passwd")
