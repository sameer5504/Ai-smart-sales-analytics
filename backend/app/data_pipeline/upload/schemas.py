from pydantic import BaseModel

from app.data_pipeline.schemas import DataType


class DataQualitySummary(BaseModel):
    """What cleaning did to an uploaded file, for the data-quality summary."""

    rows_read: int
    rows_kept: int
    values_filled: int
    rows_excluded: int
    duplicates_removed: int
    flagged_missing: dict[str, int] = {}


class ValidationSummary(BaseModel):
    """Whether the required fields were identified in the uploaded file.

    When is_valid is false the file cannot be analysed as it stands, and the
    named fields are the ones the user needs to map before it can be.
    """

    is_valid: bool
    missing_required_fields: list[str] = []


class UploadResponse(BaseModel):
    filename: str
    data_type: DataType
    size_kb: float
    extension: str
    status: str = "success"
    message: str = "file uploaded successfully"
    row_count: int | None = None
    stored: bool | None = None
    columns: list[str] | None = None
    data_quality: DataQualitySummary | None = None
    validation: ValidationSummary | None = None
