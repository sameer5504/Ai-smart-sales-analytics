"""Tests for T6.5: integrate required-field validation with real column mapping."""

import pytest

from app.data_pipeline.mapping.parser_bridge import map_parsed_file
from app.data_pipeline.schemas import DataType
from app.data_pipeline.validation.mapping_bridge import (
    build_validation_input,
    map_and_validate_required_fields,
)


@pytest.fixture
def complete_sales_df():
    """Sales DataFrame containing all required fields using uploaded column names."""
    pd = pytest.importorskip("pandas")

    return pd.DataFrame(
        columns=[
            "Order Date",
            "Order No",
            "SKU",
            "Item",
            "Qty",
            "Unit Price ($)",
            "Product Category",
        ]
    )


@pytest.fixture
def incomplete_sales_df():
    """Sales DataFrame missing the product_id source column."""
    pd = pytest.importorskip("pandas")

    return pd.DataFrame(
        columns=[
            "Order Date",
            "Order No",
            "Item",
            "Qty",
            "Unit Price ($)",
        ]
    )


def test_build_validation_input_from_real_mapping_output(
    complete_sales_df,
) -> None:
    """T6.5: Convert the real column-mapping output to validation input."""
    mapping_result = map_parsed_file(complete_sales_df)

    result = build_validation_input(
        mapping_result,
        DataType.SALES,
    )

    assert result["data_type"] == "sales"
    assert result["mapped_fields"]["Order Date"] == "transaction_date"
    assert result["mapped_fields"]["Order No"] == "order_id"
    assert result["mapped_fields"]["SKU"] == "product_id"
    assert result["mapped_fields"]["Qty"] == "quantity"


def test_complete_real_mapping_passes_required_field_validation(
    complete_sales_df,
) -> None:
    """T6.5: Real mapping output with all required fields passes validation."""
    result = map_and_validate_required_fields(
        complete_sales_df,
        DataType.SALES,
    )

    assert result["is_valid"] is True
    assert result["missing_required_fields"] == []


def test_incomplete_real_mapping_fails_required_field_validation(
    incomplete_sales_df,
) -> None:
    """T6.5: Real mapping output reports required fields that are missing."""
    result = map_and_validate_required_fields(
        incomplete_sales_df,
        DataType.SALES,
    )

    assert result["is_valid"] is False
    assert "product_id" in result["missing_required_fields"]


def test_string_data_type_is_supported(
    complete_sales_df,
) -> None:
    """T6.5: Integration accepts the string representation of a data type."""
    result = map_and_validate_required_fields(
        complete_sales_df,
        "sales",
    )

    assert result["data_type"] == "sales"
    assert result["is_valid"] is True


def test_unsupported_data_type_is_rejected(
    complete_sales_df,
) -> None:
    """T6.5: Unsupported data types keep validator behaviour unchanged."""
    with pytest.raises(
        ValueError,
        match="Unsupported data type",
    ):
        map_and_validate_required_fields(
            complete_sales_df,
            "unknown",
        )
