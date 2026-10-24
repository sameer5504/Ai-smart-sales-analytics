from src.mapping.matcher import AUTO_ACCEPT, match_columns


def _by_column(results):
    return {r["column"]: r for r in results}


def test_exact_headers_all_recognised():
    headers = ["transaction_date", "order_id", "product_id",
               "product_name", "quantity", "unit_price", "category"]
    res = _by_column(match_columns(headers))
    for h in headers:
        assert res[h]["field"] == h
        assert res[h]["confidence"] == 1.0


def test_known_aliases():
    res = _by_column(match_columns(["Order Date", "Qty", "Item", "SKU"]))
    assert res["Order Date"]["field"] == "transaction_date"
    assert res["Qty"]["field"] == "quantity"
    assert res["Item"]["field"] == "product_name"
    assert res["SKU"]["field"] == "product_id"


def test_punctuation_and_case_tolerated():
    res = _by_column(match_columns(["Unit Price ($)", "  ORDER_NO  "]))
    assert res["Unit Price ($)"]["field"] == "unit_price"
    assert res["  ORDER_NO  "]["field"] == "order_id"


def test_unrecognised_column_not_forced():
    res = _by_column(match_columns(["Notes"]))
    assert res["Notes"]["field"] is None


def test_duplicate_claims_resolved():
    res = _by_column(match_columns(["quantity", "Qty"]))
    assigned = [r for r in res.values() if r["field"] == "quantity"]
    assert len(assigned) == 1
    assert assigned[0]["column"] == "quantity"


def test_empty_headers():
    res = _by_column(match_columns(["", "   "]))
    assert all(r["field"] is None for r in res.values())


def test_low_confidence_below_auto_accept():
    res = _by_column(match_columns(["Customer Feedback Score"]))
    assert res["Customer Feedback Score"]["confidence"] < AUTO_ACCEPT


def test_messy_fixture_headers():
    headers = ["Order Date", "Order No", "SKU", "Item",
               "Qty", "Unit Price ($)", "Product Category", "Notes"]
    res = _by_column(match_columns(headers))
    mapped = [r["field"] for r in res.values() if r["field"]]
    assert len(mapped) == 7
    assert len(set(mapped)) == 7          # no field claimed twice
    assert res["Notes"]["field"] is None