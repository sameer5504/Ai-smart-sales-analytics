from typing import Literal

from pydantic import BaseModel, Field


class chatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatbotQuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user's natural-language business question.",
    )
    dataset_id: int = Field(
        ...,
        description="The id of the dataset (from GET /api/datasets) to answer questions from.",
    )
    history: list[chatMessage] = Field(
        default_factory=list,
        description="Previous messages in this session, oldest first.",
    )

    currency: str = Field(
        ...,
        description="Currency selected by the user during file upload.",
    )


class ChatbotDisplayTable(BaseModel):
    type: Literal["table"]
    title: str
    columns: list[str]
    rows: list[list]


class ChatbotDisplaySeries(BaseModel):
    name: str
    values: list[float]


class ChatbotDisplayChart(BaseModel):
    type: Literal["chart"]
    chart_kind: Literal["bar", "line"]
    title: str
    labels: list[str]
    series: list[ChatbotDisplaySeries]


class ChatbotDisplayMetricChange(BaseModel):
    type: Literal["metric_change"]
    label: str
    current_period: str | None = None
    previous_period: str | None = None
    current_value: float
    previous_value: float
    change_pct: float
    unit: str


class ChatbotDisplayInsufficientData(BaseModel):
    type: Literal["insufficient_data"]
    reason: str


class ChatbotAnswerResponse(BaseModel):
    answer: str
    display: (
        ChatbotDisplayTable | ChatbotDisplayChart | ChatbotDisplayMetricChange | ChatbotDisplayInsufficientData | None
    ) = None
