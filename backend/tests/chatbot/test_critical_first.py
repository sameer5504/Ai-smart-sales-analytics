"""Urgent findings are put in front of the assistant first (US-5.8.3).

The fixtures already come back critical-first, so the ordering tests hand in a
mixed list to prove the sort is doing the work rather than the fixture order.
"""

import json
from unittest.mock import patch

from app.chatbot.grounding import (
    DATA_CLOSE,
    DATA_OPEN,
    build_recommendations_note,
    critical_first,
)
from app.chatbot.service import ask_chatbot
from tests.chatbot.conftest import answering_client, recommendations_note
from tests.fixtures import recommendations as fixtures

MIXED = [
    fixtures.SUMAC_DEAD_STOCK,
    fixtures.COFFEE_DROP,
    fixtures.DATES_INCREASE,
    fixtures.STORE_DROP,
]


def _block(note: str) -> dict:
    body = note.split(DATA_OPEN)[1].split(DATA_CLOSE)[0]
    return json.loads(body)


def test_critical_ones_move_to_the_front():
    ordered = critical_first(MIXED)

    assert [item.id for item in ordered[:2]] == [
        fixtures.COFFEE_DROP.id,
        fixtures.STORE_DROP.id,
    ]


def test_ranking_order_is_kept_inside_each_group():
    ordered = critical_first(MIXED)

    assert [item.priority for item in ordered] == [1, 2, 3, 4]


def test_a_list_with_no_critical_findings_is_left_alone():
    mild = [fixtures.SUMAC_DEAD_STOCK, fixtures.DATES_INCREASE]

    assert critical_first(mild) == mild


def test_the_payload_is_ordered_critical_first():
    payload = _block(build_recommendations_note(fixtures.available_result(MIXED)))

    ids = [item["id"] for item in payload["recommendations"]]

    assert ids[0] == fixtures.COFFEE_DROP.id
    assert ids[1] == fixtures.STORE_DROP.id


def test_each_recommendation_is_marked_urgent_or_not():
    payload = _block(build_recommendations_note(fixtures.available_result(MIXED)))

    marks = [item["is_critical"] for item in payload["recommendations"]]

    assert marks == [True, True, False, False]


def test_the_payload_says_how_many_are_critical():
    payload = _block(build_recommendations_note(fixtures.available_result(MIXED)))

    assert payload["critical_count"] == 2


def test_marking_does_not_drop_any_other_field():
    payload = _block(build_recommendations_note(fixtures.available_result(MIXED)))

    first = payload["recommendations"][0]

    assert first["action"] == fixtures.COFFEE_DROP.action
    assert first["rationale"] == fixtures.COFFEE_DROP.rationale
    assert first["evidence"]["revenue_at_risk"] == 3510.0
    assert first["expected_impact"]["basis"]
    assert first["finding"]["severity"] == "critical"


def test_the_note_tells_the_assistant_to_lead_with_them():
    note = build_recommendations_note(fixtures.available_result(MIXED))

    assert "lead with" in note
    assert "is_critical" in note
    assert "Keep that order" in note


def test_the_ordered_payload_is_what_reaches_the_client():
    fake = answering_client("Coffee 250g needs attention first.")

    with (
        patch(
            "app.chatbot.service.load_grounding",
            return_value=fixtures.available_result(MIXED),
        ),
        patch("app.chatbot.service.get_client", return_value=fake),
    ):
        ask_chatbot("What should I do?", user_id=1, filename="sales.csv")

    payload = _block(recommendations_note(fake))

    assert payload["recommendations"][0]["id"] == fixtures.COFFEE_DROP.id
    assert payload["critical_count"] == 2
