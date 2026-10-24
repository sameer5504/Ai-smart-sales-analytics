"""Validation of required fields after column mapping."""

from typing import Any

from app.data_pipeline.validation.field_definitions import REQUIRED_FIELDS_BY_DATA_TYPE


def validate_required_fields(mapping_result: dict[str, Any]) -> dict[str, Any]:
    """Check whether all required fields exist after column mapping.

    Args:
        mapping_result: Mapping output containing:
            - data_type: The uploaded data type, such as "sales".
            - mapped_fields: Mapping from uploaded columns to standard fields.

    Returns:
        A dictionary containing the validation result and missing fields.

    Raises:
        ValueError: If the data type is unsupported or mapped_fields is invalid.
    """
    data_type = mapping_result.get("data_type")
    mapped_fields = mapping_result.get("mapped_fields")

    if data_type not in REQUIRED_FIELDS_BY_DATA_TYPE:
        raise ValueError(f"Unsupported data type: {data_type}")

    if not isinstance(mapped_fields, dict):
        raise ValueError("mapped_fields must be a dictionary")

    required_fields = REQUIRED_FIELDS_BY_DATA_TYPE[data_type]
    mapped_standard_fields = set(mapped_fields.values())

    missing_required_fields = sorted(required_fields - mapped_standard_fields)

    return {
        "data_type": data_type,
        "is_valid": len(missing_required_fields) == 0,
        "missing_required_fields": missing_required_fields,
    }
