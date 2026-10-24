"""Pytest tests for US-1.5.1: Required Field Validation.

Tasks covered:

- T6.2: Use mock column-mapping results for independent testing.
- T6.3: Validate required fields after column mapping.
- T6.4: Distinguish alternative column names from genuinely missing fields.
"""

import pytest

from app.data_pipeline.validation.required_fields import validate_required_fields

# ---------------------------------------------------------------------
# T6.3: Validate the required fields after Mapping
# ---------------------------------------------------------------------


def test_valid_sales_mapping(
    valid_sales_mapping: dict,
) -> None:
    """T6.3: Accept a mapping containing all required Sales fields."""
    result = validate_required_fields(valid_sales_mapping)

    assert result["is_valid"] is True
    assert result["missing_required_fields"] == []


def test_sales_mapping_with_missing_fields(
    missing_fields_sales_mapping: dict,
) -> None:
    """T6.3: Detect required fields missing after mapping."""
    result = validate_required_fields(missing_fields_sales_mapping)

    assert result["is_valid"] is False
    assert result["missing_required_fields"] == [
        "order_id",
        "product_id",
    ]


def test_unsupported_data_type() -> None:
    """T6.3: Reject a data type with no defined field requirements."""
    mapping_result = {
        "data_type": "unknown",
        "mapped_fields": {},
    }

    with pytest.raises(
        ValueError,
        match="Unsupported data type",
    ):
        validate_required_fields(mapping_result)


def test_invalid_mapped_fields_type() -> None:
    """T6.3: Reject an invalid mapped_fields structure."""
    mapping_result = {
        "data_type": "sales",
        "mapped_fields": [],
    }

    with pytest.raises(
        ValueError,
        match="mapped_fields must be a dictionary",
    ):
        validate_required_fields(mapping_result)


# ---------------------------------------------------------------------
# T6.4: Distinguish different names from genuinely missing data
# ---------------------------------------------------------------------


def test_alternative_column_names_are_valid(
    alternative_names_sales_mapping: dict,
) -> None:
    """T6.4: Accept different uploaded names after successful mapping."""
    result = validate_required_fields(alternative_names_sales_mapping)

    assert result["is_valid"] is True
    assert result["missing_required_fields"] == []


def test_genuinely_missing_field_is_detected() -> None:
    """T6.4: Detect a field that has no mapped source column."""
    mapping_result = {
        "data_type": "sales",
        "mapped_fields": {
            "Sales Date": "transaction_date",
            "Invoice ID": "order_id",
            "SKU": "product_id",
            "Product": "product_name",
            "Selling Price": "unit_price",
        },
    }

    result = validate_required_fields(mapping_result)

    assert result["is_valid"] is False
    assert result["missing_required_fields"] == ["quantity"]
