import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.data_pipeline.preparation import PreparationError, prepare_upload
from app.data_pipeline.schemas import DataType
from app.data_pipeline.upload.router import MAPPING_INCOMPLETE_MESSAGE
from app.data_pipeline.upload.schemas import UploadResponse
from app.data_pipeline.upload.service import storage
from app.db.datasets_repository import find_matching_dataset, insert_dataset
from app.shared.file_utils import get_extension

from .aliases import standard_fields
from .matcher import match_columns
from .validator import MappingValidationError, validate_mapping

router = APIRouter(
    prefix="/api/mapping",
    tags=["mapping"],
    dependencies=[Depends(get_current_user)],
)


class SuggestRequest(BaseModel):
    columns: list[str]


class ManualMappingRequest(BaseModel):
    columns: list[str]
    mapping: dict[str, Optional[str]] = {}


class ApplyMappingRequest(BaseModel):
    filename: str
    data_type: DataType
    currency: str
    columns: list[str]
    mapping: dict[str, Optional[str]] = {}
    # Set by the frontend after the user confirms they want to save an
    # exact duplicate anyway (see the 409 response below) - skips the
    # duplicate check and saves unconditionally.
    force: bool = False


@router.get("/schema")
def get_schema():
    """Return the standard fields a source column can be mapped to.

    Backs the frontend's field dropdown so the list of standard fields
    (and which ones are required) only ever lives in one place:
    `data_pipeline/mapping/column_aliases.json`.
    """
    schema = standard_fields()
    return [{"key": key, "label": meta["label"], "required": meta["required"]} for key, meta in schema.items()]


@router.post("/suggest")
def suggest_mapping(payload: SuggestRequest):
    """Return the automatic best-guess mapping for a set of columns.

    This is the existing automatic matcher exposed over the API so the
    manual mapping review screen can pre-fill sensible defaults for the
    user to confirm or correct, rather than starting from a blank slate.
    """
    return {"suggestions": match_columns(payload.columns)}


@router.post("/submit")
def submit_mapping(payload: ManualMappingRequest):
    """Validate and accept a user's manual column mapping.

    Malformed requests (wrong types, missing fields) are rejected
    automatically by request validation before this handler runs. This
    handler enforces the business rules that make a structurally valid
    mapping *acceptable*: every mapped column/field must be real, no
    standard field may be claimed twice, and every required standard
    field must be mapped. This check happens server-side so it cannot be
    bypassed by the frontend.
    """
    try:
        result = validate_mapping(payload.columns, payload.mapping)
    except MappingValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"success": False, "errors": exc.errors},
        ) from exc

    return {
        "success": True,
        "message": "Mapping is valid.",
        "mapping": result,
    }


@router.post("/apply", response_model=UploadResponse)
async def apply_mapping(
    payload: ApplyMappingRequest,
    current_user: dict = Depends(get_current_user),
):
    """Finish an upload using a user-confirmed manual column mapping.

    This is the other half of the manual-mapping review screen: /submit
    only checks that a mapping is structurally valid, it never touches the
    uploaded file. This endpoint re-runs the same preparation pipeline that
    /api/upload uses, but with the user's confirmed mapping in place of the
    automatic match that could not identify every required column the
    first time. The file is looked up by the filename /api/upload already
    saved it under, so nothing needs to be re-uploaded.

    Before actually saving, this checks whether the exact same content
    (same data AND mapping, since a different mapping changes the content
    hash) under the same currency was already uploaded by this user. If so,
    and the caller hasn't set force=True, nothing is saved and a 409 is
    returned with details of the existing dataset instead - the frontend
    uses this to ask the user to confirm before creating what would be a
    genuinely redundant duplicate. This is a warning, not a hard block:
    setting force=True (after the user confirms) saves it anyway, since a
    business's data can legitimately repeat (e.g. two different months
    with identical totals).

    Once confirmed, the cleaned result is written to the authenticated
    user's own folder in the shared datasets container (see prepare_upload)
    and registered as a new row in the datasets table under this same
    user - including the currency the user selected on the upload page.
    Re-applying a mapping under the same display filename creates another
    independent dataset row rather than overwriting a previous one - see
    insert_dataset.
    """
    user_id = current_user["user_id"]

    try:
        validated = validate_mapping(payload.columns, payload.mapping)
    except MappingValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"success": False, "errors": exc.errors},
        ) from exc

    if not storage.exists(payload.filename):
        raise HTTPException(
            status_code=404,
            detail=(f"No uploaded file found named '{payload.filename}'. Upload it again and then map its columns."),
        )

    file_path = storage.get_path(payload.filename)
    # validate_mapping returns {standard_field: column}; prepare_upload
    # expects the other direction, {source_column: standard_field}.
    mapped_fields = {column: field for field, column in validated.items()}

    if not payload.force:
        try:
            preview = await prepare_upload(
                file_path,
                payload.data_type,
                user_id=user_id,
                mapped_fields=mapped_fields,
                persist=False,
            )
        except PreparationError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        if preview.stored:
            existing = find_matching_dataset(user_id, preview.content_hash, payload.currency)
            if existing is not None:
                created_at = existing["created_at"]
                raise HTTPException(
                    status_code=409,
                    detail={
                        "duplicate": True,
                        "message": "This exact file (same data, mapping, and currency) was already uploaded.",
                        "existing_dataset_id": existing["id"],
                        "existing_filename": existing["filename"],
                        "existing_created_at": (
                            created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
                        ),
                    },
                )

    try:
        prepared = await prepare_upload(
            file_path,
            payload.data_type,
            user_id=user_id,
            mapped_fields=mapped_fields,
        )
    except PreparationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if prepared.stored:
        insert_dataset(
            user_id=user_id,
            filename=payload.filename,
            blob_path=prepared.cleaned_path,
            row_count=prepared.row_count,
            stored=prepared.stored,
            currency=payload.currency,
            content_hash=prepared.content_hash,
        )

    size_kb = round(os.path.getsize(file_path) / 1024, 2)

    return UploadResponse(
        filename=payload.filename,
        size_kb=size_kb,
        extension=get_extension(payload.filename),
        data_type=payload.data_type,
        row_count=prepared.row_count,
        stored=prepared.stored,
        columns=prepared.columns,
        data_quality=prepared.cleaning.to_dict(),
        validation=prepared.validation,
        status="success" if prepared.stored else "incomplete",
        message=("file uploaded successfully" if prepared.stored else MAPPING_INCOMPLETE_MESSAGE),
    )
