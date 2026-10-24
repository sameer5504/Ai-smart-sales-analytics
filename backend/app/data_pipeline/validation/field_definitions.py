"""Field definitions derived from the canonical data type schemas."""

from app.data_pipeline.schemas import EXPECTED_SCHEMAS

REQUIRED_FIELDS_BY_DATA_TYPE = {
    data_type: frozenset(schema.required_fields.keys()) for data_type, schema in EXPECTED_SCHEMAS.items()
}


OPTIONAL_FIELDS_BY_DATA_TYPE = {
    data_type: frozenset(schema.optional_fields.keys()) for data_type, schema in EXPECTED_SCHEMAS.items()
}
