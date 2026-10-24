from __future__ import annotations


def _table(title: str, columns: list[str], rows: list[list]) -> dict:
    return {"type": "table", "title": title, "columns": columns, "rows": rows}


def _chart(title: str, chart_kind: str, labels: list[str], series: list[dict]) -> dict:
    return {
        "type": "chart",
        "chart_kind": chart_kind,
        "title": title,
        "labels": labels,
        "series": series,
    }


def _metric_change(
    *,
    label: str,
    current_period: str | None,
    previous_period: str | None,
    current_value: float,
    previous_value: float,
    change_pct: float,
    unit: str,
) -> dict:
    return {
        "type": "metric_change",
        "label": label,
        "current_period": current_period,
        "previous_period": previous_period,
        "current_value": current_value,
        "previous_value": previous_value,
        "change_pct": change_pct,
        "unit": unit,
    }


def _from_top_or_lowest(result: dict, is_arabic: bool) -> dict | None:
    products = result.get("products", [])
    if len(products) < 2:
        return None
    metric = result.get("metric", "quantity")
    key = "total_quantity" if metric == "quantity" else "total_revenue"
    if result.get("extreme") == "max":
        title = "المنتجات المتصدرة" if is_arabic else "Top Products"
    else:
        title = "المنتجات الأقل" if is_arabic else "Lowest Products"
    columns = (
        ["المنتج", "الكمية" if metric == "quantity" else "الإيراد"] if is_arabic else ["Product", metric.capitalize()]
    )
    return _table(
        title,
        columns,
        [[p["product_name"], p[key]] for p in products],
    )


def _from_compare_products(result: dict, is_arabic: bool) -> dict | None:
    items = [p for p in result.get("products", []) if p.get("status") == "ok"]
    if len(items) < 2:
        return None
    labels = [p["product_name"] for p in items]
    title = "مقارنة منتجات" if is_arabic else "Product Comparison"
    units_name = "الكمية" if is_arabic else "Units"
    revenue_name = "الإيراد" if is_arabic else "Revenue"
    return _chart(
        title,
        "bar",
        labels,
        [
            {"name": units_name, "values": [p["total_units"] for p in items]},
            {"name": revenue_name, "values": [p["total_revenue"] for p in items]},
        ],
    )


def _from_monthly_series(result: dict, months_key: str, label_field: str | None, is_arabic: bool) -> dict | None:
    months = result.get(months_key, [])
    if len(months) < 2:
        return None
    if label_field and result.get(label_field):
        title = f"مبيعات {result[label_field]}" if is_arabic else f"{result[label_field]} Sales"
    else:
        title = "المبيعات عبر الوقت" if is_arabic else "Sales Over Time"
    units_name = "الكمية" if is_arabic else "Units"
    revenue_name = "الإيراد" if is_arabic else "Revenue"
    return _chart(
        title,
        "line",
        [m["month"] for m in months],
        [
            {"name": units_name, "values": [m["units"] for m in months]},
            {"name": revenue_name, "values": [m["revenue"] for m in months]},
        ],
    )


def _from_revenue_growth(result: dict, is_arabic: bool, currency: str) -> dict | None:
    if result.get("status") != "ok":
        return None
    return _metric_change(
        label="الإيراد" if is_arabic else "Revenue",
        current_period=result.get("current_period"),
        previous_period=result.get("previous_period"),
        current_value=result.get("current_revenue"),
        previous_value=result.get("previous_revenue"),
        change_pct=result.get("revenue_growth_rate_pct"),
        # Was hardcoded to "SAR"/"ريال" - now uses the currency this specific
        # dataset was actually uploaded with, same as everywhere else in the
        # project. No default currency anywhere - it always comes from the
        # uploaded file.
        unit=currency,
    )


def _from_sales_growth(result: dict, is_arabic: bool) -> dict | None:
    if result.get("status") != "ok":
        return None
    return _metric_change(
        label="الكمية المباعة" if is_arabic else "Units sold",
        current_period=result.get("current_period"),
        previous_period=result.get("previous_period"),
        current_value=result.get("current_units"),
        previous_value=result.get("previous_units"),
        change_pct=result.get("sales_growth_rate_pct"),
        # "units" here is a count unit (units sold), not a currency - no
        # change needed, this one was never hardcoding a currency.
        unit="وحدة" if is_arabic else "units",
    )


def _from_query_sales(result: dict, is_arabic: bool) -> dict | None:
    if result.get("group_by") in (None, "none"):
        return None
    rows = result.get("results", [])
    if len(rows) < 2:
        return None
    metric = result.get("metric", "value")
    group_by = result.get("group_by")
    title = f"{metric} حسب {group_by}" if is_arabic else f"{metric.capitalize()} by {group_by}"
    return _chart(
        title,
        "bar",
        [str(r["group"]) for r in rows],
        [{"name": metric, "values": [r["value"] for r in rows]}],
    )


def _from_list_transactions(result: dict, is_arabic: bool) -> dict | None:
    txs = result.get("transactions", [])
    if len(txs) < 2:
        return None
    title = "المعاملات" if is_arabic else "Transactions"
    columns = ["التاريخ", "المنتج", "الكمية", "سعر الوحدة"] if is_arabic else ["Date", "Product", "Qty", "Unit Price"]
    return _table(
        title,
        columns,
        [[t["date"], t["product_name"], t["quantity"], t["unit_price"]] for t in txs],
    )


def _from_order_details(result: dict, is_arabic: bool) -> dict | None:
    items = result.get("items", [])
    if len(items) < 2:
        return None
    order_id = result.get("order_id", "")
    title = f"تفاصيل الطلب {order_id}" if is_arabic else f"Order Details {order_id}"
    columns = (
        ["المنتج", "الكمية", "سعر الوحدة", "إجمالي السطر"]
        if is_arabic
        else ["Product", "Qty", "Unit Price", "Line Revenue"]
    )
    return _table(
        title,
        columns,
        [[i["product_name"], i["quantity"], i["unit_price"], i["line_revenue"]] for i in items],
    )


# get_revenue_growth_rate is handled separately in suggest_display below
# since it's the only rule that needs the dataset's currency - everything
# else here stays on the plain (result, is_arabic) signature.
_RULES = {
    "get_top_product": _from_top_or_lowest,
    "get_lowest_product": _from_top_or_lowest,
    "compare_products": _from_compare_products,
    "get_monthly_breakdown": lambda r, ar: _from_monthly_series(r, "months", "product_name", ar),
    "get_product_summary": lambda r, ar: _from_monthly_series(r, "monthly_breakdown", "product_name", ar),
    "get_sales_growth_rate": _from_sales_growth,
    "query_sales": _from_query_sales,
    "list_transactions": _from_list_transactions,
    "get_order_details": _from_order_details,
}


def suggest_display(
    tool_name: str | None, result: dict | None, is_arabic: bool = False, currency: str = ""
) -> dict | None:
    if not tool_name or not result or result.get("status") != "ok":
        return None
    if tool_name == "get_revenue_growth_rate":
        return _from_revenue_growth(result, is_arabic, currency)
    rule = _RULES.get(tool_name)
    if rule is None:
        return None
    return rule(result, is_arabic)


def insufficient_data_card(reason: str) -> dict:
    return {"type": "insufficient_data", "reason": reason}


def suggest_followups(tool_name: str | None, result: dict | None, is_arabic: bool) -> list[str]:
    if not tool_name or not result or result.get("status") != "ok":
        return []

    def t(ar: str, en: str) -> str:
        return ar if is_arabic else en

    if tool_name in ("get_top_product", "get_lowest_product"):
        return [
            t("قارن هذا المنتج بمنتج آخر", "Compare this product to another"),
            t("شو نسبة نمو المبيعات؟", "What's the sales growth rate?"),
            t("أعطني تفصيل شهري لهذا المنتج", "Give me a monthly breakdown for this product"),
        ]

    if tool_name == "compare_products":
        return [
            t("شو المنتج الأعلى مبيعًا هذا الشهر؟", "What's the top-selling product this month?"),
            t("أعطيني تفصيل شهري لأحد المنتجين", "Give me a monthly breakdown for one of them"),
        ]

    if tool_name in ("get_monthly_breakdown", "get_product_summary"):
        product = result.get("product_name")
        return [
            t(
                f"وريني معاملات {product} الأخيرة" if product else "وريني آخر المعاملات",
                f"Show me recent transactions for {product}" if product else "Show me recent transactions",
            ),
            t("شو نسبة نمو الإيراد؟", "What's the revenue growth rate?"),
        ]

    if tool_name in ("get_revenue_growth_rate", "get_sales_growth_rate"):
        return [
            t("شو أعلى منتج مبيعًا الشهر الحالي؟", "What's the top product this month?"),
            t("وريني تفصيل شهري لكل المبيعات", "Show me a monthly breakdown of all sales"),
        ]

    if tool_name == "list_transactions":
        return [
            t("شو أعلى منتج بهاي الفترة؟", "What's the top product in this period?"),
            t("أعطيني ملخص لهاي الفترة", "Give me a summary for this period"),
        ]

    if tool_name == "get_order_details":
        return [
            t("وريني طلبات ثانية بنفس الشهر", "Show me other orders in the same month"),
            t("شو أعلى منتج مبيعًا؟", "What's the top-selling product?"),
        ]

    if tool_name == "get_date_range_summary":
        return [
            t("وريني تفاصيل المعاملات بهاي الفترة", "Show me the transaction details for this period"),
            t("قارن هاي الفترة بفترة ثانية", "Compare this period to another one"),
        ]

    return [
        t("شو تفاصيل الشهر الماضي؟", "What about last month's details?"),
        t("قارن بين منتجين", "Compare two products"),
    ]
