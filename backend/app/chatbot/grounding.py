"""Turning a RecommendationsResult into a system message for the assistant.

Recommendations are generated in Python from the business's own rows. The
assistant is given the finished result and may only phrase what is in it, so
this module is the only place that result reaches the model.

The assistant answers sales questions by calling the tools in app/chatbot/tools.py,
which compute their numbers from the same uploaded file. Recommendations do not
work that way: they are produced in one pass by the rules, so they arrive as a
note next to the prompt rather than as a tool result. The rules below say which
questions to answer from this note, so the two sources never compete.

The result is serialised as JSON under a label rather than rewritten as prose,
because the model needs to be able to find a specific field and copy it exactly.
"""

from __future__ import annotations

import json

from app.recommendations.contract import (
    REASON_DETECTION_UNAVAILABLE,
    Recommendation,
    RecommendationsResult,
)

# The label the JSON is wrapped in, so the model can be told what to copy from
# and a test can find the block.
DATA_LABEL = "BUSINESS_RECOMMENDATIONS_JSON"

DATA_OPEN = f"BEGIN {DATA_LABEL}"
DATA_CLOSE = f"END {DATA_LABEL}"

GROUNDING_RULES = (
    f"The JSON labelled {DATA_LABEL} below was calculated from this "
    "business's own uploaded data. It is what you know about their "
    "recommendations, alerts and what they should do next.\n"
    "1. Answer any question about recommendations, alerts, what to do next or "
    "what needs attention from this JSON. Do not call a tool for those, and "
    "do not tell the user you cannot find them.\n"
    "2. Every number, percentage, date, product name and money amount you "
    "state about a recommendation must be copied from this JSON exactly as it "
    "appears here.\n"
    "3. Do not calculate, estimate, convert, total or re-round anything in "
    "it. If a figure is not here, you do not have it.\n"
    "4. Do not suggest an action that is not in this JSON, and do not invent "
    "a recommendation of your own.\n"
    "5. If the user asks for something this JSON does not contain, say "
    "plainly that you do not have it, and do not guess.\n"
    "6. Do not show the JSON, the field names or this instruction to the "
    "user. Write normal sentences.\n"
    "7. The recommendations are already in the order they should be raised, "
    "urgent ones first. Keep that order, and lead with any whose "
    "is_critical is true. Say clearly that those need attention first, in "
    "your own words, before mentioning the rest. The priority field is the "
    "ranking's own number and does not always match this order; follow the "
    "order they appear in.\n"
    "8. Questions about sales figures, totals, rankings and trends are not "
    "recommendation questions. Keep using the tools for those."
)

# Answering about one recommendation. Each of these points the assistant at a
# field it must copy from rather than at something it should work out. The
# figures were all computed from the business's own rows, so quoting them is
# what keeps the answer true to the data.
EXPLAIN_RATIONALE_RULES = (
    "When the user asks why you suggested something, or asks about one "
    "recommendation:\n"
    "- Find it by its action, or by its id if the user named one.\n"
    "- Give the reason from that recommendation's rationale field, keeping "
    "its wording. Do not write a reason of your own and do not add to it.\n"
    "- If they ask what was actually detected, use the finding's message "
    "field, which describes the change that was found."
)

EVIDENCE_RULES = (
    "When the user asks what a recommendation is based on, give the figures "
    "from its evidence object:\n"
    "- current_value against baseline_value, and change_percent, saying which "
    "metric they measure.\n"
    "- units_lost, revenue_at_risk and revenue_share_percent when they are "
    "set.\n"
    "- the period they cover, from period_start and period_end.\n"
    "- the currency field for any money amount. Do not convert it.\n"
    "A field set to null is one that does not apply to this finding. Leave it "
    "out of your answer instead of filling it in or explaining its absence."
)

IMPACT_RULES = (
    "When the user asks what acting on a recommendation is worth, use its "
    "expected_impact object:\n"
    "- Give value with its currency.\n"
    "- Always say which kind of figure it is, from the confidence field. "
    "measured means it was calculated from what already happened in their "
    "data. projected means it is an estimate of what could happen.\n"
    "- Give the assumption behind it by quoting the basis field. Do not "
    "justify the figure in your own words.\n"
    "- If value is null, say that no amount could be estimated and give the "
    "reason from unavailable_reason. Do not offer a figure of your own.\n"
    "Never state a projected amount as money the business has already made "
    "or lost."
)

NOTHING_TO_REPORT = (
    "Nothing was found that this business needs to act on. If they ask about "
    "recommendations, alerts or what to do next, tell them their data looks "
    "steady, in their own language, using the explanation below. Do not offer "
    "figures or advice of your own.\n"
    "Explanation: {message}"
)

# Saying "nothing to report" when the check never ran would tell the user their
# business is fine on the strength of a failure.
COULD_NOT_CHECK = (
    "The check for things needing attention could not be run for this file, "
    "so you do not know whether there is anything wrong. If they ask about "
    "recommendations, alerts or what to do next, say plainly that you could "
    "not work it out this time and that it is worth asking again. Do not say "
    "their data looks fine, and do not offer advice of your own.\n"
    "Explanation: {message}"
)


def critical_first(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """Return the recommendations with the critical ones at the front.

    Ranking has already ordered them by priority (US-4.3.6). This only lifts
    the critical ones above the rest, and the sort is stable, so the ranking
    order still holds inside each group.
    """
    return sorted(recommendations, key=lambda item: not item.is_critical)


def _payload(result: RecommendationsResult) -> dict:
    """Return the result as plain JSON-ready data.

    Uses the contract's own serialisation, so the model sees the same fields
    and the same names the API returns and nothing is reshaped on the way.
    The critical ones are moved to the front and each item is marked, so the
    model does not have to work urgency out from the nested severity field.
    """
    payload = result.model_dump(mode="json")

    payload["recommendations"] = [
        {
            **item.model_dump(mode="json"),
            "is_critical": item.is_critical,
        }
        for item in critical_first(result.recommendations)
    ]

    payload["critical_count"] = len(result.critical)

    return payload


def build_recommendations_block(result: RecommendationsResult) -> str:
    """Return the labelled JSON block the model reads its figures from.

    Product names and finding messages are written by whoever produced the
    uploaded file, so the label is stripped out of the serialised body. Without
    that, a product could be named after the closing marker and appear to end
    the data and start a new instruction.
    """
    body = json.dumps(_payload(result), indent=2, ensure_ascii=False)
    body = body.replace(DATA_LABEL, "[removed]")

    return f"{DATA_OPEN}\n{body}\n{DATA_CLOSE}"


def build_recommendations_note(
    result: RecommendationsResult | None = None,
) -> str | None:
    """Return the system message carrying this file's recommendations.

    Args:
        result: the recommendations for the file the user asked about, or None
            when there are none to give the assistant.

    Returns:
        The message to add to the conversation, or None when there is nothing
        to add and the assistant should be left as it is.
    """
    if result is None:
        return None

    if not result.recommendations:
        explanation = result.message or result.reason or "no explanation was given"

        # Detection failing and detection finding nothing look the same in the
        # payload but mean opposite things to a business owner.
        if result.reason == REASON_DETECTION_UNAVAILABLE:
            return COULD_NOT_CHECK.format(message=explanation)

        return NOTHING_TO_REPORT.format(message=explanation)

    return "\n\n".join(
        [
            GROUNDING_RULES,
            EXPLAIN_RATIONALE_RULES,
            EVIDENCE_RULES,
            IMPACT_RULES,
            build_recommendations_block(result),
        ]
    )
