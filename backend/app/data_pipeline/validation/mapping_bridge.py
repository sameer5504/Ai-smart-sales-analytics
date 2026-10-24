"""Integration between column mapping and required-field validation."""

from typing import Any

from app.data_pipeline.mapping.parser_bridge import map_parsed_file
from app.data_pipeline.schemas import DataType
from app.data_pipeline.validation.required_fields import validate_required_fields


def build_validation_input(
    mapping_result: dict[str, Any],
    data_type: DataType | str,
) -> dict[str, Any]:
    """Convert a mapping result into the input expected by required-field validation."""
    recognised = mapping_result.get("recognised", [])

    mapped_fields = {item["column"]: item["suggested_field"] for item in recognised if item.get("suggested_field")}

    normalised_data_type = data_type.value if isinstance(data_type, DataType) else data_type

    return {
        "data_type": normalised_data_type,
        "mapped_fields": mapped_fields,
    }


def validate_mapping_required_fields(
    mapping_result: dict[str, Any],
    data_type: DataType | str,
) -> dict[str, Any]:
    """Validate required fields using the real column-mapping output."""
    validation_input = build_validation_input(
        mapping_result,
        data_type,
    )

    return validate_required_fields(validation_input)


def map_and_validate_required_fields(
    parsed: Any,
    data_type: DataType | str,
) -> dict[str, Any]:
    """Run real column mapping, then validate the mapped required fields."""
    mapping_result = map_parsed_file(parsed)

    return validate_mapping_required_fields(
        mapping_result,
        data_type,
    )
