import json
import logging
from collections.abc import Iterator

from openai import AzureOpenAI

from app.chatbot import display, grounding, tools
from app.chatbot.schemas import chatMessage
from app.core import config as settings
from app.recommendations.contract import RecommendationsResult
from app.recommendations.provider import load_recommendations

logger = logging.getLogger(__name__)

deployment = settings.AZURE_OPENAI_DEPLOYMENT

INSUFFICIENT_DATA_MESSAGE = {
    "ar": "عذرًا، لا تتوفر لدي بيانات كافية للإجابة على هذا السؤال حاليًا.",
    "en": "Sorry, I don't have enough data to answer this question right now.",
}

_MAX_TOOL_ITERATIONS = 5

_TOOL_STEP_LABELS: dict[str, dict[str, str]] = {
    "get_total_revenue": {"ar": "جاري حساب الإيراد", "en": "Calculating revenue"},
    "get_total_units": {"ar": "جاري حساب عدد الوحدات", "en": "Calculating units sold"},
    "get_top_product": {"ar": "جاري ترتيب المنتجات", "en": "Ranking products"},
    "get_lowest_product": {"ar": "جاري ترتيب المنتجات", "en": "Ranking products"},
    "compare_products": {"ar": "جاري مقارنة المنتجات", "en": "Comparing products"},
    "list_transactions": {"ar": "جاري جلب المعاملات", "en": "Fetching transactions"},
    "get_number_of_orders": {"ar": "جاري عدّ الطلبات", "en": "Counting orders"},
    "get_average_order_value": {
        "ar": "جاري حساب متوسط قيمة الطلب",
        "en": "Calculating average order value",
    },
    "get_revenue_growth_rate": {
        "ar": "جاري حساب نسبة نمو الإيراد",
        "en": "Calculating revenue growth",
    },
    "get_sales_growth_rate": {
        "ar": "جاري حساب نسبة نمو المبيعات",
        "en": "Calculating sales growth",
    },
    "get_product_summary": {"ar": "جاري تجهيز ملخص المنتج", "en": "Building product summary"},
    "get_monthly_breakdown": {
        "ar": "جاري مراجعة البيانات الشهرية",
        "en": "Reviewing monthly data",
    },
    "get_date_range_summary": {
        "ar": "جاري مراجعة الفترة المحددة",
        "en": "Reviewing selected period",
    },
    "get_order_details": {"ar": "جاري جلب تفاصيل الطلب", "en": "Fetching order details"},
    "get_available_data_overview": {
        "ar": "جاري التحقق من البيانات المتوفرة",
        "en": "Checking available data",
    },
    "query_sales": {"ar": "جاري تنفيذ الاستعلام", "en": "Running query"},
}


def _step_label(tool_name: str, is_arabic: bool) -> str:
    labels = _TOOL_STEP_LABELS.get(tool_name)
    if not labels:
        return "جاري المعالجة" if is_arabic else "Working on it"
    return labels["ar" if is_arabic else "en"]


SYSTEM_PROMPT_TEMPLATE = (
    "You are a business analytics assistant for a small business owner.\n"
    "---\n"
    "HOW YOU WORK:\n"
    "- You do NOT have the raw business data in this prompt. Instead, you have "
    "a set of tools (functions) that compute exact numbers directly from the "
    "business's real transaction database.\n"
    "- For ANY question that needs a number, a calculation, a comparison, a "
    "ranking, a trend, or a listing of transactions, you MUST call the "
    "appropriate tool. NEVER calculate, sum, estimate, or guess a number "
    "yourself - always get it from a tool call.\n"
    "- NEVER invent, alter, or reconstruct a transaction, order, product, "
    "date, or value that a tool did not return to you. If a tool result does "
    "not contain something, it does not exist - say so, don't make it up.\n"
    "- If you are not sure whether a month or product name the user mentioned "
    "actually exists in the data, call get_available_data_overview first "
    "instead of guessing or assuming.\n"
    "- Product names passed to tools MUST match exactly as they appear in "
    "the data (e.g. from get_available_data_overview or a previous tool "
    "result) - do NOT translate or localize a product name before passing "
    "it to a tool, even if you're responding in Arabic. Display the "
    "product name to the user in whichever language fits your response, "
    "but always pass the original data value to tool calls.\n"
    "- If no named tool fits the question, use query_sales as a general "
    "fallback before giving up.\n"
    "- If a tool returns status 'unavailable', 'not_found', or "
    "'not_comparable', clearly tell the user what is missing. Do not guess "
    "or fill in a plausible-sounding number.\n"
    "- Every new question - even if it looks similar to a previous one (a "
    "different month, a different product, a follow-up like 'and in "
    "August?') - needs its OWN fresh tool call with the new parameters. "
    "NEVER reuse a number from an earlier tool result for a different "
    "month/product/period, even if it seems like a safe guess.\n"
    "- If the user challenges a number you gave (in any language, e.g. "
    "'غلط', 'wrong', 'are you sure'), you MUST call the relevant tool again "
    "before responding - do not just repeat or rephrase your previous "
    "answer, and do not simply agree with the user's suggested number "
    "without verifying it via a tool call.\n"
    "- If the question is unrelated to the business's sales data, politely "
    "decline and say you can only help with questions about the user's "
    "business data.\n"
    "- Do not use markdown formatting in your answer - no **bold**, no "
    "bullet points with -, no headers, no numbered lists. Write plain "
    "prose sentences only, with numbers and product names written inline.\n"
    "- Keep answers under 100 words, clear and concise. Perform all "
    "calculations via tools only, and present just the final result unless "
    "the user explicitly asks to see the underlying transactions.\n"
    "- When the user asks to see transactions/orders and a tool returns a "
    "list of them, do NOT restate every row in prose - the data is already "
    "shown as a table. Just give a short 1-2 sentence summary (e.g. count, "
    "date range, or a notable pattern) and let the table carry the detail.\n"
    "- Always respond in the same language as the user's question (Arabic or "
    "English).\n"
)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = AzureOpenAI(
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.get_azure_openai_api_key(),
        )
    return _client


def _is_arabic(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in text)


def load_grounding(
    user_id: int,
    filename: str | None,
) -> RecommendationsResult | None:
    """Return the recommendations to ground this answer in.

    Reads only this user's own prepared rows, so the assistant can never be
    grounded in someone else's data. A file that has not been prepared is not
    an error here: the assistant still answers, without recommendations,
    rather than refusing the question.

    Args:
        user_id: the authenticated user, from the request rather than the
            client.
        filename: the stored blob name of the dataset being asked about.

    Returns:
        The RecommendationsResult for that dataset, or None when there is no
        dataset or its rows could not be read.
    """
    if not filename:
        return None

    try:
        return load_recommendations(user_id, filename)

    except Exception:
        # Grounding is additive. The tools have already answered for this
        # file, so a problem here costs the recommendations and nothing else.
        logger.warning(
            "Could not load recommendations for %s, answering without them",
            filename,
            exc_info=True,
        )
        return None


def _stream_completion(client, messages, tool_choice) -> Iterator[tuple[str, object]]:
    """
    Streams a single chat-completion call.

    Yields ("token", text) live as plain-text content arrives.
    Yields exactly one final event when the stream ends:
      - ("tool_calls", [ {id, name, arguments}, ... ])  if the model wants tools
      - ("final_content", full_text)                     if the model is done
    """
    response_stream = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=tools.TOOLS_SCHEMA,
        tool_choice=tool_choice,
        max_tokens=1024,
        temperature=0.3,
        stream=True,
    )

    tool_calls_acc: dict[int, dict] = {}
    content_acc = ""

    for chunk in response_stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        if getattr(delta, "tool_calls", None):
            for tc in delta.tool_calls:
                slot = tool_calls_acc.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments

        if getattr(delta, "content", None):
            content_acc += delta.content
            yield ("token", delta.content)

    if tool_calls_acc:
        ordered = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
        yield ("tool_calls", ordered)
    else:
        yield ("final_content", content_acc)


def _run_tool_call(user_id: int, filename: str, name: str, arguments_json: str) -> dict:
    func = tools.TOOL_DISPATCH.get(name)
    if func is None:
        return {"status": "error", "reason": f"unknown tool: {name}"}
    try:
        arguments = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        return {"status": "error", "reason": "invalid arguments JSON"}
    try:
        return func(user_id=user_id, filename=filename, **arguments)
    except TypeError as e:
        return {"status": "error", "reason": f"invalid arguments for {name}: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "reason": str(e)}


def ask_chatbot_stream(
    question: str,
    user_id: int,
    filename: str,
    history: list[chatMessage] | None = None,
    currency: str = "",
) -> Iterator[dict]:
    """
    Runs the tool-calling loop and yields NDJSON-ready event dicts:
      {"type": "step", "tool": ..., "label": ...}
      {"type": "token", "text": ...}
      {"type": "done", "answer": ..., "display": ..., "suggestions": ...}
    """
    history = history or []
    is_arabic = _is_arabic(question)

    try:
        overview = tools.get_available_data_overview(user_id, filename)
        if overview.get("status") != "ok":
            yield {
                "type": "done",
                "answer": INSUFFICIENT_DATA_MESSAGE["ar" if is_arabic else "en"],
                "display": display.insufficient_data_card(overview.get("reason", "no data")),
            }
            return

        client = get_client()

        overview_note = (
            "GROUND TRUTH - the ONLY months, products, and date range that "
            "actually exist in this user's data (use this instead of "
            "guessing a year or checking if something exists yourself):\n"
            f"{json.dumps(overview, ensure_ascii=False, default=str)}"
        )

        currency_note = (
            f"The currency selected by the user for this uploaded data is {currency}. "
            "When presenting monetary values, use this exact currency. "
            "Do not assume, replace, or convert it to another currency."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
            {"role": "system", "content": currency_note},
            {"role": "system", "content": overview_note},
        ]

        # Recommendations come from the rules in one pass rather than from a
        # tool, so they are given to the model here. The note says which
        # questions to answer from it, so it does not compete with the tools.
        recommendations_note = grounding.build_recommendations_note(load_grounding(user_id, filename))

        if recommendations_note:
            messages.append({"role": "system", "content": recommendations_note})

        messages += [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": question})

        last_tool_name: str | None = None
        last_tool_result: dict | None = None

        for iteration in range(_MAX_TOOL_ITERATIONS):
            forced_first_call = iteration == 0
            tool_choice = "required" if forced_first_call else "auto"

            tool_calls = None
            final_text = None

            for kind, payload in _stream_completion(client, messages, tool_choice):
                if kind == "token":
                    yield {"type": "token", "text": payload}
                elif kind == "tool_calls":
                    tool_calls = payload
                elif kind == "final_content":
                    final_text = payload

            if tool_calls is None:
                display_block = display.suggest_display(last_tool_name, last_tool_result, is_arabic, currency)
                followups = display.suggest_followups(last_tool_name, last_tool_result, is_arabic)
                yield {
                    "type": "done",
                    "answer": final_text,
                    "display": display_block,
                    "suggestions": followups,
                }
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                yield {
                    "type": "step",
                    "tool": tc["name"],
                    "label": _step_label(tc["name"], is_arabic),
                }

                result = _run_tool_call(user_id, filename, tc["name"], tc["arguments"])
                last_tool_name = tc["name"]
                last_tool_result = result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

        yield {
            "type": "done",
            "answer": INSUFFICIENT_DATA_MESSAGE["ar" if is_arabic else "en"],
            "display": None,
        }

    except Exception:
        message = (
            "عذرًا، حصل خطأ أثناء معالجة سؤالك. حاول مرة أخرى."
            if is_arabic
            else "Sorry, something went wrong while processing your question. Please try again."
        )
        yield {"type": "done", "answer": message, "display": None, "error": True}


def ask_chatbot(
    question: str,
    user_id: int,
    filename: str,
    history: list[chatMessage] | None = None,
    currency: str = "",
) -> dict:
    """
    Non-streaming convenience wrapper around ask_chatbot_stream, kept for
    Swagger testing and any caller that doesn't need live streaming.
    Collects the stream and returns just the final {"answer", "display"}.
    """
    final = {"answer": "", "display": None}

    for event in ask_chatbot_stream(question, user_id, filename, history, currency):
        if event.get("type") == "done":
            final = {"answer": event.get("answer"), "display": event.get("display")}
    return final
