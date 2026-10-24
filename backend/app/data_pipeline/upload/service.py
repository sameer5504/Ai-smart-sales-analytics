import logging

from fastapi import HTTPException, UploadFile

from app.shared.file_utils import get_extension
from app.storage.local_storage import LocalStorage

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_FILE_SIZE_MB = 25
BYTES_PER_KB = 1024
BYTES_PER_MB = 1024 * 1024

storage = LocalStorage(base_dir="uploads")


async def validate_and_save_file(file: UploadFile) -> dict:
    extension = get_extension(file.filename)

    if extension not in ALLOWED_EXTENSIONS:
        logger.warning("Rejected %s: extension %s not allowed", file.filename, extension)
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    contents = await file.read()
    size_bytes = len(contents)

    if not contents:
        logger.warning("Rejected %s: file is empty", file.filename)
        raise HTTPException(
            status_code=400,
            detail="The file is empty.",
        )

    if size_bytes > MAX_FILE_SIZE_MB * BYTES_PER_MB:
        logger.warning(
            "Rejected %s: %.2fMB exceeds the %dMB limit",
            file.filename,
            size_bytes / BYTES_PER_MB,
            MAX_FILE_SIZE_MB,
        )
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds the allowed limit ({MAX_FILE_SIZE_MB}MB)",
        )

    saved_path = await storage.save(file.filename, contents)
    logger.info("Saved %s (%.2fKB) to %s", file.filename, size_bytes / BYTES_PER_KB, saved_path)

    return {
        "filename": file.filename,
        "size_kb": round(size_bytes / BYTES_PER_KB, 2),
        "extension": extension,
        "saved_path": saved_path,
    }