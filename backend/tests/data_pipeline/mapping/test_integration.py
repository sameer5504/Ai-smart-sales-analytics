import pytest

from app.data_pipeline.mapping.parser_bridge import extract_headers, map_parsed_file
from app.data_pipeline.parsing import parse_file

MESSY_HEADERS = ["Order Date", "Order No", "SKU", "Item", "Qty", "Unit Price ($)", "Product Category", "Notes"]

CLEAN_HEADERS = ["transaction_date", "order_id", "product_id", "product_name", "quantity", "unit_price", "category"]


@pytest.fixture
def messy_df():
    """DataFrame with headers as they appear in a real business export."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame(
        [["2026-01-05", 1001, "P-11", "Blue Mug", 3, 12.50, "Kitchen", "gift wrap"]],
        columns=MESSY_HEADERS,
    )


@pytest.fixture
def clean_df():
    """DataFrame already using the standard field names."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame(
        [["2026-01-05", 1001, "P-11", "Blue Mug", 3, 12.50, "Kitchen"]],
        columns=CLEAN_HEADERS,
    )


@pytest.fixture
def unmappable_df():
    """DataFrame whose headers match no standard field."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame([[1, 2, 3, 4]], columns=["Col1", "Col2", "Col3", "Col4"])


def test_extract_from_dataframe(messy_df):
    assert extract_headers(messy_df) == MESSY_HEADERS


def test_messy_dataframe_returns_contract(messy_df):
    r = map_parsed_file(messy_df)
    assert len(r["recognised"]) == 7
    assert [c["column"] for c in r["unrecognised"]] == ["Notes"]
    assert r["ready_for_analysis"] is True
    assert r["column_count"] == 8


def test_clean_dataframe_all_recognised(clean_df):
    r = map_parsed_file(clean_df)
    assert len(r["recognised"]) == 7
    assert r["unmapped_required_fields"] == []


def test_unmappable_dataframe_rejected(unmappable_df):
    r = map_parsed_file(unmappable_df)
    assert r["ready_for_analysis"] is False
    assert len(r["unmapped_required_fields"]) == 6


def test_extract_from_dict_shape():
    assert extract_headers({"headers": MESSY_HEADERS, "rows": []}) == MESSY_HEADERS


def test_extract_from_list_of_dicts():
    assert extract_headers([{h: None for h in MESSY_HEADERS}]) == MESSY_HEADERS


def test_extract_rejects_unknown_shape():
    with pytest.raises(ValueError):
        extract_headers("not tabular")


def test_numeric_headers_coerced_to_string():
    r = map_parsed_file({"headers": [2026, "Qty"], "rows": []})
    assert r["column_count"] == 2


def test_parse_file_output_maps_successfully(tmp_path, messy_df):
    """The real parser output should be accepted directly by the mapping bridge."""
    file_path = tmp_path / "sales.csv"
    messy_df.to_csv(file_path, index=False)

    parsed = parse_file(str(file_path))
    result = map_parsed_file(parsed)

    assert result["column_count"] == 8
    assert len(result["recognised"]) == 7
    assert [c["column"] for c in result["unrecognised"]] == ["Notes"]
