import io

import pytest
from fastapi import HTTPException, UploadFile

from app.data_pipeline.upload.service import validate_and_save_file


def make_upload_file(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content))


@pytest.mark.asyncio
async def test_valid_csv_file_is_saved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    file = make_upload_file("data.csv", b"a,b,c\n1,2,3")
    result = await validate_and_save_file(file)

    assert result["filename"] == "data.csv"
    assert result["extension"] == ".csv"
    assert result["size_kb"] > 0


@pytest.mark.asyncio
async def test_rejects_disallowed_extension(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    file = make_upload_file("document.pdf", b"%PDF-1.4")

    with pytest.raises(HTTPException) as exc_info:
        await validate_and_save_file(file)

    assert exc_info.value.status_code == 400
    assert "not supported" in exc_info.value.detail


@pytest.mark.asyncio
async def test_rejects_file_over_size_limit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    large_content = b"x" * (26 * 1024 * 1024)
    file = make_upload_file("big.csv", large_content)

    with pytest.raises(HTTPException) as exc_info:
        await validate_and_save_file(file)

    assert exc_info.value.status_code == 400
    assert "exceeds" in exc_info.value.detail