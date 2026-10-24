from app.data_pipeline.mapping.contract import build_mapping_result


def test_clean_file_all_recognised_and_ready():
    headers = ["transaction_date", "order_id", "product_id", "product_name", "quantity", "unit_price", "category"]
    r = build_mapping_result(headers)
    assert len(r["recognised"]) == 7
    assert r["unrecognised"] == []
    assert r["unmapped_required_fields"] == []
    assert r["ready_for_analysis"] is True


def test_messy_file_recognised_with_junk_column():
    headers = ["Order Date", "Order No", "SKU", "Item", "Qty", "Unit Price ($)", "Product Category", "Notes"]
    r = build_mapping_result(headers)
    assert len(r["recognised"]) == 7
    assert [c["column"] for c in r["unrecognised"]] == ["Notes"]
    assert r["ready_for_analysis"] is True


def test_missing_required_field_reported_by_name():
    headers = ["Order Date", "Order No", "Item", "Qty", "Unit Price"]
    r = build_mapping_result(headers)
    assert "product_id" in r["unmapped_required_fields"]
    assert r["ready_for_analysis"] is False


def test_optional_category_absence_does_not_block():
    headers = ["transaction_date", "order_id", "product_id", "product_name", "quantity", "unit_price"]
    r = build_mapping_result(headers)
    assert r["unmapped_required_fields"] == []
    assert r["ready_for_analysis"] is True


def test_unmappable_file_everything_unrecognised():
    r = build_mapping_result(["Col1", "Col2", "Col3", "Col4"])
    assert r["recognised"] == []
    assert len(r["unmapped_required_fields"]) == 6
    assert r["ready_for_analysis"] is False


def test_every_column_appears_exactly_once():
    headers = ["Order Date", "Notes", "Qty", "Random"]
    r = build_mapping_result(headers)
    total = r["recognised"] + r["ambiguous"] + r["unrecognised"]
    assert len(total) == len(headers)
