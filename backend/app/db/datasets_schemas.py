from datetime import datetime

from pydantic import BaseModel


class DatasetSummary(BaseModel):
    id: int
    filename: str
    row_count: int | None = None
    currency: str | None = None
    created_at: datetime


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]
