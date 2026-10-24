import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.chatbot.schemas import ChatbotAnswerResponse, ChatbotQuestionRequest
from app.chatbot.service import ask_chatbot, ask_chatbot_stream
from app.db.datasets_repository import get_dataset_for_user

router = APIRouter(
    prefix="/chatbot",
    tags=["chatbot"],
    dependencies=[Depends(get_current_user)],
)


def _validate_question(payload: ChatbotQuestionRequest) -> str:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    return question


def _resolve_owned_filename(dataset_id: int, user_id: int) -> str:
    dataset = get_dataset_for_user(dataset_id, user_id)
    if dataset is None:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this dataset.",
        )
    # blob_path looks like "datasets/user-13/a1b2c3d4_sales.csv" - we need
    # just the stored blob's own name (what AzureStorage/load_cleaned
    # expects), not the display filename, since one display filename can
    # now have several uploads stored behind it.
    return dataset["blob_path"].rsplit("/", 1)[-1]


def _ndjson_generator(
    question: str,
    user_id: int,
    filename: str,
    history,
    currency: str,
) -> Iterator[str]:
    for event in ask_chatbot_stream(
        question,
        user_id=user_id,
        filename=filename,
        history=history,
        currency=currency,
    ):
        yield json.dumps(event, ensure_ascii=False, default=str) + "\n"


@router.post("/ask/stream")
def ask_question_stream(
    payload: ChatbotQuestionRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    question = _validate_question(payload)
    user_id = current_user["user_id"]
    filename = _resolve_owned_filename(payload.dataset_id, user_id)

    return StreamingResponse(
        _ndjson_generator(
            question,
            user_id,
            filename,
            payload.history,
            payload.currency,
        ),
        media_type="application/x-ndjson",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )


@router.post("/ask", response_model=ChatbotAnswerResponse)
def ask_question(
    payload: ChatbotQuestionRequest,
    current_user: dict = Depends(get_current_user),
) -> ChatbotAnswerResponse:
    question = _validate_question(payload)
    user_id = current_user["user_id"]
    filename = _resolve_owned_filename(payload.dataset_id, user_id)

    result = ask_chatbot(
        question,
        user_id=user_id,
        filename=filename,
        history=payload.history,
        currency=payload.currency,
    )
    return ChatbotAnswerResponse(answer=result["answer"], display=result["display"])
