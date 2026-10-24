import pytest

from app.data_pipeline.mapping.matcher import AUTO_ACCEPT, match_columns


def _by_column(results):
    return {r["column"]: r for r in results}


@pytest.mark.parametrize(
    "header",
    [
        "transaction_date",
        "order_id",
        "product_id",
        "product_name",
        "quantity",
        "unit_price",
        "category",
    ],
)
def test_exact_headers_all_recognised(header):
    res = _by_column(match_columns([header]))
    assert res[header]["field"] == header
    assert res[header]["confidence"] == 1.0


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Order Date", "transaction_date"),
        ("Qty", "quantity"),
        ("Item", "product_name"),
        ("SKU", "product_id"),
    ],
)
def test_known_aliases(header, expected):
    assert _by_column(match_columns([header]))[header]["field"] == expected


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Unit Price ($)", "unit_price"),
        ("  ORDER_NO  ", "order_id"),
    ],
)
def test_punctuation_and_case_tolerated(header, expected):
    assert _by_column(match_columns([header]))[header]["field"] == expected


@pytest.mark.parametrize("header", ["Notes", "", "   "])
def test_unrecognised_or_empty_not_forced(header):
    assert _by_column(match_columns([header]))[header]["field"] is None


def test_duplicate_claims_resolved():
    res = _by_column(match_columns(["quantity", "Qty"]))
    assigned = [r for r in res.values() if r["field"] == "quantity"]
    assert len(assigned) == 1
    assert assigned[0]["column"] == "quantity"


def test_low_confidence_below_auto_accept():
    res = _by_column(match_columns(["Customer Feedback Score"]))
    assert res["Customer Feedback Score"]["confidence"] < AUTO_ACCEPT


def test_realistic_export_headers():
    """Headers as they appear in a typical business export."""
    headers = ["Order Date", "Order No", "SKU", "Item", "Qty", "Unit Price ($)", "Product Category", "Notes"]
    res = _by_column(match_columns(headers))
    mapped = [r["field"] for r in res.values() if r["field"]]
    assert len(mapped) == 7
    assert len(set(mapped)) == 7
    assert res["Notes"]["field"] is None
