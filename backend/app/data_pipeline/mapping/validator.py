"""Validation for a user-submitted (manual) column mapping.

This intentionally reuses the same schema source as the automatic matcher
(`aliases.standard_fields`) so manual and automatic mapping never disagree
about which fields exist or which ones are required.
"""

from .aliases import standard_fields


class MappingValidationError(Exception):
    """Raised when a manual mapping fails validation.

    `errors` is a dict of error-code -> details, so callers (e.g. the API
    layer) can surface every problem at once instead of one at a time.
    """

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__("Invalid column mapping")


def validate_mapping(columns, mapping, schema=None) -> dict:
    """Validate a manual mapping of source columns to standard fields.

    Args:
        columns: list of source column headers (as parsed from the file).
        mapping: dict of ``column_name -> standard_field_key`` (or ``None``
            for a column the user left unmapped). Columns absent from this
            dict are treated as unmapped.
        schema: optional schema override, defaults to the shared
            ``standard_fields()`` configuration.

    Returns:
        dict of ``standard_field_key -> column_name`` for every mapped
        field on success.

    Raises:
        MappingValidationError: with a structured ``errors`` dict describing
        every problem found. Possible keys:
            - ``unknown_columns``: mapping keys not present in ``columns``.
            - ``unknown_fields``: mapped values that aren't valid standard
              fields.
            - ``duplicate_field_mapping``: a standard field claimed by more
              than one column.
            - ``missing_required_fields``: required standard fields with no
              column mapped to them.
    """
    schema = schema or standard_fields()
    errors: dict = {}

    columns_set = set(columns)
    unknown_columns = sorted(set(mapping) - columns_set)
    if unknown_columns:
        errors["unknown_columns"] = unknown_columns

    unknown_fields = sorted({field for field in mapping.values() if field is not None and field not in schema})
    if unknown_fields:
        errors["unknown_fields"] = unknown_fields

    field_to_columns: dict = {}
    for column, field in mapping.items():
        if field is None or field in unknown_fields or column in unknown_columns:
            continue
        field_to_columns.setdefault(field, []).append(column)

    duplicates = {field: cols for field, cols in field_to_columns.items() if len(cols) > 1}
    if duplicates:
        errors["duplicate_field_mapping"] = duplicates

    required_fields = [field for field, meta in schema.items() if meta["required"]]
    mapped_fields = set(field_to_columns)
    missing_required = sorted(field for field in required_fields if field not in mapped_fields)
    if missing_required:
        errors["missing_required_fields"] = missing_required

    if errors:
        raise MappingValidationError(errors)

    return {field: cols[0] for field, cols in field_to_columns.items()}
