import pytest

from src.mapping.validator import MappingValidationError, validate_mapping

COLUMNS = ["Order Date", "Order No", "SKU", "Item", "Qty", "Unit Price", "Notes"]
FULL_MAPPING = {
    "Order Date": "transaction_date",
    "Order No": "order_id",
    "SKU": "product_id",
    "Item": "product_name",
    "Qty": "quantity",
    "Unit Price": "unit_price",
}


def test_valid_mapping_returns_field_to_column():
    result = validate_mapping(COLUMNS, FULL_MAPPING)
    assert result["order_id"] == "Order No"
    assert result["unit_price"] == "Unit Price"
    assert "category" not in result


def test_missing_required_field_raises_with_field_name():
    mapping = dict(FULL_MAPPING)
    del mapping["Qty"]  # quantity is required
    with pytest.raises(MappingValidationError) as exc_info:
        validate_mapping(COLUMNS, mapping)
    assert exc_info.value.errors["missing_required_fields"] == ["quantity"]


def test_all_required_missing_when_mapping_is_empty():
    with pytest.raises(MappingValidationError) as exc_info:
        validate_mapping(COLUMNS, {})
    missing = exc_info.value.errors["missing_required_fields"]
    assert set(missing) == {
        "transaction_date", "order_id", "product_id",
        "product_name", "quantity", "unit_price",
    }


def test_unknown_column_is_rejected():
    with pytest.raises(MappingValidationError) as exc_info:
        validate_mapping(COLUMNS, {**FULL_MAPPING, "Does Not Exist": "category"})
    assert exc_info.value.errors["unknown_columns"] == ["Does Not Exist"]


def test_unknown_field_is_rejected():
    mapping = dict(FULL_MAPPING)
    mapping["Notes"] = "not_a_real_field"
    with pytest.raises(MappingValidationError) as exc_info:
        validate_mapping(COLUMNS, mapping)
    assert exc_info.value.errors["unknown_fields"] == ["not_a_real_field"]


def test_duplicate_field_assignment_is_rejected():
    mapping = dict(FULL_MAPPING)
    mapping["Notes"] = "order_id"  # order_id already claimed by "Order No"
    with pytest.raises(MappingValidationError) as exc_info:
        validate_mapping(COLUMNS, mapping)
    duplicates = exc_info.value.errors["duplicate_field_mapping"]
    assert set(duplicates["order_id"]) == {"Order No", "Notes"}


def test_optional_field_may_be_left_unmapped():
    mapping = dict(FULL_MAPPING)
    mapping["Notes"] = None
    result = validate_mapping(COLUMNS, mapping)
    assert "category" not in result
