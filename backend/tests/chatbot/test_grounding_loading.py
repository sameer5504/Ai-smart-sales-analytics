"""The answer is grounded in the recommendations for the file being asked about.

Loading is checked here. What the prompt does with the result is covered in
tests/chatbot/test_prompt.py.
"""

from unittest.mock import patch

from app.chatbot.service import ask_chatbot, load_grounding
from tests.chatbot.conftest import answering_client, recommendations_note
from tests.fixtures import recommendations as fixtures


def test_no_dataset_loads_nothing():
    assert load_grounding(1, None) is None
    assert load_grounding(1, "") is None


def test_the_rows_are_read_as_the_asking_user():
    """The user id is passed through, so grounding cannot cross accounts."""
    with patch(
        "app.chatbot.service.load_recommendations",
        return_value=fixtures.available_result(),
    ) as loader:
        result = load_grounding(13, "a1b2c3d4_sales.csv")

    loader.assert_called_once_with(13, "a1b2c3d4_sales.csv")
    assert result.recommendations


def test_an_unprepared_file_answers_without_recommendations():
    with patch(
        "app.chatbot.service.load_recommendations",
        side_effect=FileNotFoundError("no prepared data"),
    ):
        assert load_grounding(1, "never-uploaded.csv") is None


def test_an_unreadable_dataset_answers_without_recommendations():
    with patch(
        "app.chatbot.service.load_recommendations",
        side_effect=ValueError("Invalid filename"),
    ):
        assert load_grounding(1, "../secrets/sales.csv") is None


def test_the_dataset_being_asked_about_is_the_one_loaded():
    fake = answering_client()

    with (
        patch(
            "app.chatbot.service.load_grounding",
            return_value=fixtures.available_result(),
        ) as loader,
        patch("app.chatbot.service.get_client", return_value=fake),
    ):
        ask_chatbot("What should I do?", user_id=13, filename="a1b2c3d4_sales.csv")

    loader.assert_called_once_with(13, "a1b2c3d4_sales.csv")


def test_an_unprepared_file_still_gets_an_answer():
    fake = answering_client("I can still help with your sales figures.")

    with (
        patch("app.chatbot.service.load_grounding", return_value=None),
        patch("app.chatbot.service.get_client", return_value=fake),
    ):
        result = ask_chatbot("Hello", user_id=1, filename="sales.csv")

    assert result["answer"] == "I can still help with your sales figures."
    assert recommendations_note(fake) is None
