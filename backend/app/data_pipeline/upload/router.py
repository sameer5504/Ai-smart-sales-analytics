import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import get_current_user
from app.data_pipeline.preparation import PreparationError, prepare_upload
from app.data_pipeline.schemas import DataType
from app.data_pipeline.upload.schemas import UploadResponse
from app.data_pipeline.upload.service import validate_and_save_file
from app.services.anomaly_detection_service import detect_anomalies

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/upload",
    tags=["Upload"],
    dependencies=[Depends(get_current_user)],
)

MAPPING_INCOMPLETE_MESSAGE = (
    "We could not identify every required column, so the file was not saved. Map the missing fields and upload again."
)


@router.post("", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    data_type: DataType = Form(...),
    currency: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Validate the uploaded file and preview how it would be prepared.

    This is a PREVIEW only - nothing is written to Azure or registered in
    the datasets table here, even when the automatic column match succeeds
    completely. The frontend always sends every upload through a review
    step next, and that step's confirm action (/api/mapping/apply) is the
    single place a dataset actually gets saved. Persisting here as well
    would save the same upload twice (two dataset rows for one upload the
    user experienced as a single action) - see prepare_upload's `persist`
    parameter.
    """
    user_id = current_user["user_id"]

    file_info = await validate_and_save_file(file)

    try:
        prepared = await prepare_upload(
            file_info["saved_path"],
            data_type,
            user_id=user_id,
            persist=False,
        )
    except PreparationError as exc:
        logger.warning(
            "Upload %s rejected for user %s: %s",
            file_info["filename"],
            user_id,
            exc,
        )
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if prepared.stored and data_type == DataType.SALES:
        anomalies = detect_anomalies(prepared.dataframe)

        logger.info(
            "Detected %d anomalies for %s",
            len(anomalies),
            file_info["filename"],
        )

    return UploadResponse(
        filename=file_info["filename"],
        size_kb=file_info["size_kb"],
        extension=file_info["extension"],
        data_type=data_type,
        row_count=prepared.row_count,
        stored=prepared.stored,
        columns=prepared.columns,
        data_quality=prepared.cleaning.to_dict(),
        validation=prepared.validation,
        status="success" if prepared.stored else "incomplete",
        message=("file uploaded successfully" if prepared.stored else MAPPING_INCOMPLETE_MESSAGE),
    )
