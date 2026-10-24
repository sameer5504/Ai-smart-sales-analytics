"""Shared helpers for the chatbot tests.

The assistant streams its answer and calls tools on the way, so a test that
wants to see the system messages has to stand in for a streamed response
rather than a single completion.
"""

from unittest.mock import MagicMock, patch

import pytest

import app.chatbot.service as chatbot_service


@pytest.fixture(autouse=True)
def reset_client():
    chatbot_service._client = None
    yield
    chatbot_service._client = None


@pytest.fixture(autouse=True)
def no_stored_rows():
    """Keep the assistant's recommendation grounding away from storage.

    Every answer now loads the dataset's recommendations for the system
    prompt, which reads from blob storage. A test that has not said what its
    stored rows are should not reach for them, so grounding is off unless the
    test asks for it. Tests about grounding patch this again with what they
    want back.
    """
    with patch("app.chatbot.service.load_grounding", return_value=None):
        yield


@pytest.fixture(autouse=True)
def fake_data_overview():
    """Stand in for the tool that checks the file has usable rows."""
    with patch(
        "app.chatbot.service.tools.get_available_data_overview",
        return_value={
            "status": "ok",
            "available_months": ["2026-06", "2026-07"],
            "available_products": ["Coffee 250g", "Dates 1kg"],
            "earliest_date": "2026-06-01",
            "latest_date": "2026-07-31",
        },
    ):
        yield


def make_stream_chunk(content=None):
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = None

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def answering_client(text: str = "Here is what stands out."):
    """A client that answers straight away without asking for a tool."""
    fake = MagicMock()
    fake.chat.completions.create.return_value = [make_stream_chunk(content=text)]
    return fake


def sent_messages(fake) -> list[dict]:
    """Return the messages the service sent on its first call."""
    return fake.chat.completions.create.call_args.kwargs["messages"]


def system_messages(fake) -> list[str]:
    return [message["content"] for message in sent_messages(fake) if message["role"] == "system"]


def recommendations_note(fake) -> str | None:
    """Return the system message carrying the recommendations, if there is one.

    Found by what it says rather than by its position, because the assistant's
    other system messages are not ours and more of them get added over time.
    """
    from app.chatbot.grounding import DATA_LABEL

    for message in system_messages(fake):
        if DATA_LABEL in message:
            return message

    return None
