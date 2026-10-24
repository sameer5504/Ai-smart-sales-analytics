from unittest.mock import MagicMock, patch

import pytest

import app.chatbot.service as chatbot_service
from app.chatbot.service import ask_chatbot

TEST_USER_ID = 1


def make_tool_call_delta(index: int, call_id: str, name: str, arguments: str = "{}"):
    """Simulates one streamed tool_call delta (as if it all arrived in one chunk)."""
    tc = MagicMock()
    tc.index = index
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def make_stream_chunk(content=None, tool_call_deltas=None):
    """Simulates one chunk of a streamed chat-completion response."""
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_call_deltas

    choice = MagicMock()
    choice.delta = delta

    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def make_tool_call_stream(call_id: str, name: str, arguments: str = "{}"):
    """A full streamed response that only requests a tool call (no content)."""
    return [make_stream_chunk(tool_call_deltas=[make_tool_call_delta(0, call_id, name, arguments)])]


def make_content_stream(text: str):
    """A full streamed response containing the final answer text, in one chunk."""
    return [make_stream_chunk(content=text)]


@pytest.fixture(autouse=True)
def reset_client():
    chatbot_service._client = None
    yield
    chatbot_service._client = None


@pytest.fixture(autouse=True)
def fake_data_overview():
    with patch(
        "app.chatbot.service.tools.get_available_data_overview",
        return_value={
            "status": "ok",
            "available_months": ["2026-06", "2026-07"],
            "available_products": ["Mouse", "Keyboard"],
            "earliest_date": "2026-06-01",
            "latest_date": "2026-07-31",
            "total_valid_transactions": 50,
            "total_orders": 30,
        },
    ):
        yield


@pytest.fixture()
def fake_tool_result():
    with patch(
        "app.chatbot.service.tools.TOOL_DISPATCH",
        {"get_total_revenue": MagicMock(return_value={"status": "ok", "month": "all_time", "total_revenue": 1000.0})},
    ):
        yield


@patch("app.chatbot.service.settings.get_azure_openai_api_key")
@patch("app.chatbot.service.AzureOpenAI")
def test_azure_connection(mock_azure_openai, mock_get_key, fake_tool_result):
    mock_get_key.return_value = "fake-api-key"

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        make_tool_call_stream("call_1", "get_total_revenue"),
        make_content_stream("Yes, I am working!"),
    ]
    mock_azure_openai.return_value = mock_client

    result = ask_chatbot(
        "Hello, can you confirm that you are working?",
        user_id=TEST_USER_ID,
        filename="sales_2026.xlsx",
    )

    assert result["answer"] == "Yes, I am working!"
    assert mock_client.chat.completions.create.call_count == 2


@patch("app.chatbot.service.settings.get_azure_openai_api_key")
@patch("app.chatbot.service.AzureOpenAI")
def test_arabic_question(mock_azure_openai, mock_get_key, fake_tool_result):
    mock_get_key.return_value = "fake-api-key"

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        make_tool_call_stream("call_1", "get_total_revenue"),
        make_content_stream("أعلى شهر مبيعات كان يناير."),
    ]
    mock_azure_openai.return_value = mock_client

    result = ask_chatbot(
        "شو كان أعلى شهر مبيعات؟",
        user_id=TEST_USER_ID,
        filename="sales_2026.xlsx",
    )

    assert result["answer"] == "أعلى شهر مبيعات كان يناير."


@patch("app.chatbot.service.settings.get_azure_openai_api_key")
@patch("app.chatbot.service.AzureOpenAI")
def test_azure_failure_returns_friendly_message(mock_azure_openai, mock_get_key):
    mock_get_key.return_value = "fake-api-key"

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("network error")
    mock_azure_openai.return_value = mock_client

    result = ask_chatbot("Hello", user_id=TEST_USER_ID, filename="sales_2026.xlsx")

    assert "Sorry" in result["answer"]


@patch("app.chatbot.service.settings.get_azure_openai_api_key")
@patch("app.chatbot.service.AzureOpenAI")
def test_no_data_skips_azure_entirely(mock_azure_openai, mock_get_key):
    mock_get_key.return_value = "fake-api-key"
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    with patch(
        "app.chatbot.service.tools.get_available_data_overview",
        return_value={"status": "unavailable", "reason": "no valid data for this user"},
    ):
        result = ask_chatbot("Hello", user_id=TEST_USER_ID, filename="nonexistent.xlsx")

    assert result["display"]["type"] == "insufficient_data"
    mock_client.chat.completions.create.assert_not_called()
