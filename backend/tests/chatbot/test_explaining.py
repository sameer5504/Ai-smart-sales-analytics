"""Explaining a recommendation in chat (US-5.4.1, US-5.4.2, US-5.4.3).

The assistant is told to quote three things rather than write them: why a
recommendation was generated, the figures behind it, and what acting on it is
worth. These check the instruction is there and that the field it points at is
actually in the payload, so a rule can never refer to something the model was
not given.
"""

import json
from unittest.mock import patch

from app.chatbot.grounding import (
    DATA_CLOSE,
    DATA_OPEN,
    EVIDENCE_RULES,
    EXPLAIN_RATIONALE_RULES,
    IMPACT_RULES,
    build_recommendations_note,
)
from app.chatbot.service import ask_chatbot
from tests.chatbot.conftest import answering_client, recommendations_note
from tests.fixtures import recommendations as fixtures


def _payload() -> dict:
    note = build_recommendations_note(fixtures.available_result())
    body = note.split(DATA_OPEN)[1].split(DATA_CLOSE)[0]
    return json.loads(body)


def _find(payload: dict, recommendation_id: str) -> dict:
    return next(item for item in payload["recommendations"] if item["id"] == recommendation_id)


def test_the_assistant_is_told_to_quote_the_rationale():
    prompt = build_recommendations_note(fixtures.available_result())

    assert EXPLAIN_RATIONALE_RULES in prompt
    assert "rationale field" in prompt
    assert "Do not write a reason of your own" in prompt


def test_the_rationale_and_the_finding_message_are_both_available():
    coffee = _find(_payload(), fixtures.COFFEE_DROP.id)

    assert coffee["rationale"] == fixtures.COFFEE_DROP.rationale
    assert coffee["finding"]["message"] == fixtures.COFFEE_DROP.finding.message


def test_a_recommendation_can_be_found_by_id():
    ids = [item["id"] for item in _payload()["recommendations"]]

    assert fixtures.COFFEE_DROP.id in ids
    assert len(set(ids)) == len(ids)


def test_the_assistant_is_told_which_evidence_figures_to_give():
    prompt = build_recommendations_note(fixtures.available_result())

    assert EVIDENCE_RULES in prompt

    for field in [
        "current_value",
        "baseline_value",
        "change_percent",
        "units_lost",
        "revenue_at_risk",
        "revenue_share_percent",
        "period_start",
        "period_end",
        "currency",
    ]:
        assert field in prompt


def test_the_evidence_figures_are_in_the_payload():
    evidence = _find(_payload(), fixtures.COFFEE_DROP.id)["evidence"]

    assert evidence["metric"] == "units_sold"
    assert evidence["current_value"] == 42.0
    assert evidence["baseline_value"] == 120.0
    assert evidence["change_percent"] == -65.0
    assert evidence["units_lost"] == 78.0
    assert evidence["revenue_at_risk"] == 3510.0
    assert evidence["revenue_share_percent"] == 22.4
    assert evidence["period_start"] == "2026-07-20"
    assert evidence["currency"] == "GBP"


def test_the_assistant_is_told_to_leave_null_evidence_out():
    prompt = build_recommendations_note(fixtures.available_result())

    assert "does not apply to this finding" in prompt
    assert "Leave it out" in prompt


def test_a_finding_with_no_baseline_carries_nulls_rather_than_zeroes():
    evidence = _find(_payload(), fixtures.SUMAC_DEAD_STOCK.id)["evidence"]

    assert evidence["baseline_value"] is None
    assert evidence["change_percent"] is None
    assert evidence["current_value"] == 0.0


def test_the_assistant_must_label_the_impact_measured_or_projected():
    prompt = build_recommendations_note(fixtures.available_result())

    assert IMPACT_RULES in prompt
    assert "confidence field" in prompt
    assert "measured means" in prompt
    assert "projected means" in prompt
    assert "basis field" in prompt


def test_a_projected_impact_carries_its_label_and_basis():
    impact = _find(_payload(), fixtures.COFFEE_DROP.id)["expected_impact"]

    assert impact["value"] == 3510.0
    assert impact["currency"] == "GBP"
    assert impact["confidence"] == "projected"
    assert impact["basis"] == fixtures.COFFEE_DROP.expected_impact.basis


def test_a_measured_impact_is_labelled_differently():
    impact = _find(_payload(), fixtures.STORE_DROP.id)["expected_impact"]

    assert impact["confidence"] == "measured"


def test_an_impact_with_no_value_carries_its_reason():
    impact = _find(_payload(), fixtures.DATES_INCREASE.id)["expected_impact"]

    assert impact["value"] is None
    assert impact["unavailable_reason"] == "insufficient_history"
    assert impact["basis"]


def test_the_assistant_is_told_what_to_do_with_a_missing_impact():
    prompt = build_recommendations_note(fixtures.available_result())

    assert "no amount could be estimated" in prompt
    assert "unavailable_reason" in prompt
    assert "Do not offer a figure of your own" in prompt


def test_a_projection_may_not_be_stated_as_something_that_happened():
    prompt = build_recommendations_note(fixtures.available_result())

    assert "already made" in prompt


def test_the_explanation_rules_reach_the_client():
    fake = answering_client("It was suggested because sales fell 65%.")

    with (
        patch(
            "app.chatbot.service.load_grounding",
            return_value=fixtures.available_result(),
        ),
        patch("app.chatbot.service.get_client", return_value=fake),
    ):
        ask_chatbot("Why did you suggest that?", user_id=1, filename="sales.csv")

    note = recommendations_note(fake)

    assert EXPLAIN_RATIONALE_RULES in note
    assert EVIDENCE_RULES in note
    assert IMPACT_RULES in note


def test_an_empty_result_gets_no_explanation_rules():
    prompt = build_recommendations_note(fixtures.empty_result())

    assert EXPLAIN_RATIONALE_RULES not in prompt
    assert EVIDENCE_RULES not in prompt
    assert IMPACT_RULES not in prompt
