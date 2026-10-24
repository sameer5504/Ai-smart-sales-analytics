from __future__ import annotations

import pandas as pd

from app.data_pipeline.preparation import load_cleaned

_ROW_LIMIT = 10_000


def _load_df(user_id: int, filename: str) -> pd.DataFrame:
    df = load_cleaned(user_id, filename)

    df["quantity"] = pd.to_numeric(df["quantity"])
    df["unit_price"] = pd.to_numeric(df["unit_price"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    df["line_revenue"] = df["quantity"] * df["unit_price"]

    df["product_id"] = df["product_id"].astype(str)
    df["order_id"] = df["order_id"].astype(str)

    df["month"] = df["transaction_date"].dt.strftime("%Y-%m")

    return df


def _filter_by_month(df: pd.DataFrame, month: str | None) -> pd.DataFrame:
    if not month:
        return df
    return df[df["month"] == month]


def _product_display_name(df: pd.DataFrame, product_id: str) -> str:
    names = df.loc[df["product_id"] == product_id, "product_name"]
    return names.iloc[0] if not names.empty else product_id


def _match_product(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """
    matches a product name against df["product_name"], case-insensitively
    tries an exact match first; if that finds nothing, falls back to a
    substring match. This guards against the model passing a translated
    or slightly different form of the product name than what's in the data
    """
    target = name.strip().lower()
    subset = df[df["product_name"].str.lower() == target]
    if subset.empty:
        subset = df[df["product_name"].str.lower().str.contains(target, regex=False)]
    return subset


def get_total_revenue(user_id: int, filename: str, month: str | None = None) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    if df.empty:
        return {"status": "unavailable", "month": month, "reason": "no valid data"}
    return {
        "status": "ok",
        "month": month or "all_time",
        "total_revenue": round(float(df["line_revenue"].sum()), 2),
    }


def get_total_units(user_id: int, filename: str, month: str | None = None) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    if df.empty:
        return {"status": "unavailable", "month": month, "reason": "no valid data"}
    return {
        "status": "ok",
        "month": month or "all_time",
        "total_units": int(df["quantity"].sum()),
    }


def _rank_products(df: pd.DataFrame, metric: str, extreme: str) -> dict:
    """metric: 'quantity' or 'revenue'. extreme: 'max' or 'min'."""
    if df.empty:
        return {"status": "unavailable", "reason": "no valid data"}

    value_col = "quantity" if metric == "quantity" else "line_revenue"
    grouped = df.groupby("product_id")[value_col].sum()

    target = grouped.max() if extreme == "max" else grouped.min()
    winners = grouped[grouped == target]

    products = [
        {
            "product_id": pid,
            "product_name": _product_display_name(df, pid),
            "total_quantity" if metric == "quantity" else "total_revenue": round(float(val), 2),
        }
        for pid, val in winners.items()
    ]
    return {"status": "ok", "metric": metric, "extreme": extreme, "products": products}


def get_top_product(user_id: int, filename: str, month: str | None = None, metric: str = "quantity") -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    result = _rank_products(df, metric, "max")
    result["month"] = month or "all_time"
    return result


def get_lowest_product(user_id: int, filename: str, month: str | None = None, metric: str = "quantity") -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    result = _rank_products(df, metric, "min")
    result["month"] = month or "all_time"
    return result


def compare_products(user_id: int, filename: str, product_names: list[str], month: str | None = None) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    if df.empty:
        return {"status": "unavailable", "reason": "no valid data"}

    results = []
    for name in product_names:
        subset = _match_product(df, name)
        if subset.empty:
            results.append({"product_name": name, "status": "not_found"})
            continue
        results.append(
            {
                "product_name": name,
                "status": "ok",
                "total_units": int(subset["quantity"].sum()),
                "total_revenue": round(float(subset["line_revenue"].sum()), 2),
            }
        )

    return {"status": "ok", "month": month or "all_time", "products": results}


def list_transactions(
    user_id: int,
    filename: str,
    product_name: str | None = None,
    month: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    if product_name:
        df = _match_product(df, product_name)

    if date_from:
        start = pd.to_datetime(date_from, errors="coerce")
        if not pd.isna(start):
            df = df[df["transaction_date"] >= start]
    if date_to:
        end = pd.to_datetime(date_to, errors="coerce")
        if not pd.isna(end):
            df = df[df["transaction_date"] <= end]

    if df.empty:
        return {"status": "unavailable", "reason": "no matching transactions"}

    safe_limit = max(1, min(limit, 50))
    df = df.sort_values("transaction_date", ascending=False).head(safe_limit)

    rows = [
        {
            "date": row["transaction_date"].strftime("%Y-%m-%d"),
            "order_id": row["order_id"],
            "product_name": row["product_name"],
            "quantity": int(row["quantity"]),
            "unit_price": float(row["unit_price"]),
        }
        for _, row in df.iterrows()
    ]
    return {
        "status": "ok",
        "count": len(rows),
        "truncated": safe_limit < limit,
        "transactions": rows,
    }


def get_number_of_orders(user_id: int, filename: str, month: str | None = None) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    if df.empty:
        return {"status": "unavailable", "month": month, "reason": "no valid data"}
    return {
        "status": "ok",
        "month": month or "all_time",
        "number_of_orders": int(df["order_id"].nunique()),
    }


def get_average_order_value(user_id: int, filename: str, month: str | None = None) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    if df.empty:
        return {"status": "unavailable", "month": month, "reason": "no valid data"}

    order_revenue = df.groupby("order_id")["line_revenue"].sum()
    if order_revenue.empty:
        return {"status": "unavailable", "month": month, "reason": "no valid revenue orders"}

    return {
        "status": "ok",
        "month": month or "all_time",
        "average_order_value": round(float(order_revenue.mean()), 2),
        "orders_counted": int(order_revenue.shape[0]),
    }


def _available_months_sorted(df: pd.DataFrame) -> list[str]:
    months = df["month"].dropna().unique().tolist()
    return sorted(months)


def get_revenue_growth_rate(user_id: int, filename: str) -> dict:
    df = _load_df(user_id, filename)
    months = _available_months_sorted(df)
    if len(months) < 2:
        return {"status": "unavailable", "reason": "fewer than two months with valid data"}

    current, previous = months[-1], months[-2]
    current_rev = float(df[df["month"] == current]["line_revenue"].sum())
    previous_rev = float(df[df["month"] == previous]["line_revenue"].sum())

    if previous_rev == 0:
        return {
            "status": "not_comparable",
            "current_period": current,
            "previous_period": previous,
            "reason": "previous period revenue is zero",
        }

    growth = ((current_rev - previous_rev) / previous_rev) * 100
    return {
        "status": "ok",
        "current_period": current,
        "previous_period": previous,
        "current_revenue": round(current_rev, 2),
        "previous_revenue": round(previous_rev, 2),
        "revenue_growth_rate_pct": round(growth, 2),
    }


def get_sales_growth_rate(user_id: int, filename: str) -> dict:
    df = _load_df(user_id, filename)
    months = _available_months_sorted(df)
    if len(months) < 2:
        return {"status": "unavailable", "reason": "fewer than two months with valid data"}

    current, previous = months[-1], months[-2]
    current_units = float(df[df["month"] == current]["quantity"].sum())
    previous_units = float(df[df["month"] == previous]["quantity"].sum())

    if previous_units == 0:
        return {
            "status": "not_comparable",
            "current_period": current,
            "previous_period": previous,
            "reason": "previous period units is zero",
        }

    growth = ((current_units - previous_units) / previous_units) * 100
    return {
        "status": "ok",
        "current_period": current,
        "previous_period": previous,
        "current_units": current_units,
        "previous_units": previous_units,
        "sales_growth_rate_pct": round(growth, 2),
    }


def get_product_summary(user_id: int, filename: str, product_name: str, month: str | None = None) -> dict:
    df = _filter_by_month(_load_df(user_id, filename), month)
    subset = _match_product(df, product_name)
    if subset.empty:
        return {"status": "not_found", "product_name": product_name, "month": month or "all_time"}

    monthly = (
        subset.groupby("month")
        .agg(units=("quantity", "sum"), revenue=("line_revenue", "sum"))
        .reset_index()
        .sort_values("month")
    )

    return {
        "status": "ok",
        "product_name": product_name,
        "month_filter": month or "all_time",
        "total_units": int(subset["quantity"].sum()),
        "total_revenue": round(float(subset["line_revenue"].sum()), 2),
        "orders_count": int(subset["order_id"].nunique()),
        "average_unit_price": round(float(subset["unit_price"].mean()), 2),
        "first_sale_date": subset["transaction_date"].min().strftime("%Y-%m-%d"),
        "last_sale_date": subset["transaction_date"].max().strftime("%Y-%m-%d"),
        "monthly_breakdown": [
            {"month": r["month"], "units": int(r["units"]), "revenue": round(float(r["revenue"]), 2)}
            for _, r in monthly.iterrows()
        ],
    }


def get_monthly_breakdown(user_id: int, filename: str, product_name: str | None = None) -> dict:
    df = _load_df(user_id, filename)
    if product_name:
        df = _match_product(df, product_name)

    if df.empty:
        return {"status": "unavailable", "reason": "no matching data"}

    monthly = (
        df.groupby("month")
        .agg(units=("quantity", "sum"), revenue=("line_revenue", "sum"))
        .reset_index()
        .sort_values("month")
    )

    return {
        "status": "ok",
        "product_name": product_name or "all_products",
        "months": [
            {"month": r["month"], "units": int(r["units"]), "revenue": round(float(r["revenue"]), 2)}
            for _, r in monthly.iterrows()
        ],
    }


def get_date_range_summary(user_id: int, filename: str, date_from: str, date_to: str) -> dict:
    df = _load_df(user_id, filename)
    start = pd.to_datetime(date_from, errors="coerce")
    end = pd.to_datetime(date_to, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return {"status": "error", "reason": "invalid date_from/date_to format, use YYYY-MM-DD"}

    subset = df[(df["transaction_date"] >= start) & (df["transaction_date"] <= end)]
    if subset.empty:
        return {"status": "unavailable", "reason": "no transactions in this range"}

    top = _rank_products(subset, "quantity", "max")

    return {
        "status": "ok",
        "date_from": date_from,
        "date_to": date_to,
        "total_revenue": round(float(subset["line_revenue"].sum()), 2),
        "total_units": int(subset["quantity"].sum()),
        "number_of_orders": int(subset["order_id"].nunique()),
        "transaction_count": int(len(subset)),
        "top_product_by_quantity": top.get("products", []),
    }


def get_order_details(user_id: int, filename: str, order_id: str) -> dict:
    df = _load_df(user_id, filename)
    subset = df[df["order_id"] == str(order_id).strip()]
    if subset.empty:
        return {"status": "not_found", "order_id": order_id}

    items = [
        {
            "product_name": row["product_name"],
            "quantity": int(row["quantity"]),
            "unit_price": float(row["unit_price"]),
            "line_revenue": round(float(row["line_revenue"]), 2),
        }
        for _, row in subset.iterrows()
    ]
    return {
        "status": "ok",
        "order_id": order_id,
        "date": subset["transaction_date"].iloc[0].strftime("%Y-%m-%d"),
        "items": items,
        "order_total_revenue": round(float(subset["line_revenue"].sum()), 2),
        "order_total_units": int(subset["quantity"].sum()),
    }


def get_available_data_overview(user_id: int, filename: str) -> dict:
    df = _load_df(user_id, filename)
    if df.empty:
        return {"status": "unavailable", "reason": "no valid data for this user"}

    return {
        "status": "ok",
        "available_months": _available_months_sorted(df),
        "available_products": sorted(df["product_name"].dropna().unique().tolist()),
        "earliest_date": df["transaction_date"].min().strftime("%Y-%m-%d"),
        "latest_date": df["transaction_date"].max().strftime("%Y-%m-%d"),
        "total_valid_transactions": int(len(df)),
        "total_orders": int(df["order_id"].nunique()),
    }


def query_sales(
    user_id: int,
    filename: str,
    product_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    group_by: str = "none",
    metric: str = "revenue",
) -> dict:
    df = _load_df(user_id, filename)

    if product_name:
        df = _match_product(df, product_name)
    if date_from:
        start = pd.to_datetime(date_from, errors="coerce")
        if not pd.isna(start):
            df = df[df["transaction_date"] >= start]
    if date_to:
        end = pd.to_datetime(date_to, errors="coerce")
        if not pd.isna(end):
            df = df[df["transaction_date"] <= end]

    if df.empty:
        return {"status": "unavailable", "reason": "no transactions match these filters"}

    metric_col = {"revenue": "line_revenue", "units": "quantity"}.get(metric)

    def _metric_value(sub: pd.DataFrame) -> float:
        if metric == "transaction_count":
            return float(len(sub))
        return float(sub[metric_col].sum())

    if group_by == "none":
        return {
            "status": "ok",
            "metric": metric,
            "filters": {"product_name": product_name, "date_from": date_from, "date_to": date_to},
            "value": round(_metric_value(df), 2),
        }

    group_col = {"product": "product_name", "month": "month"}.get(group_by)
    if group_col is None and group_by == "day":
        df = df.copy()
        df["day"] = df["transaction_date"].dt.strftime("%Y-%m-%d")
        group_col = "day"
    if group_col is None:
        return {"status": "error", "reason": "group_by must be one of: none, product, month, day"}

    if metric == "transaction_count":
        grouped = df.groupby(group_col).size()
    else:
        grouped = df.groupby(group_col)[metric_col].sum()

    grouped = grouped.sort_values(ascending=False).head(50)

    return {
        "status": "ok",
        "metric": metric,
        "group_by": group_by,
        "filters": {"product_name": product_name, "date_from": date_from, "date_to": date_to},
        "results": [{"group": k, "value": round(float(v), 2)} for k, v in grouped.items()],
    }


# NOTE ON TOOLS_SCHEMA (unchanged below):
# `user_id` is intentionally NOT a parameter here. This schema is what the LLM
# sees and can populate — user_id must never be something the model chooses or
# supplies. It comes only from the authenticated session/JWT and is injected
# by app/chatbot/service.py (_run_tool_call) when it calls TOOL_DISPATCH,
# alongside `filename` which is already resolved server-side from dataset_id
# via the ownership check. See the accompanying note for the exact call shape.

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_total_revenue",
            "description": "احسبي إجمالي الإيراد (revenue) لشهر محدد أو لكل الفترة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {
                        "type": "string",
                        "description": "الشهر بصيغة YYYY-MM، أو اتركيه فاضي لكل الفترة.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_total_units",
            "description": "احسبي إجمالي عدد الوحدات المباعة لشهر محدد أو لكل الفترة.",
            "parameters": {
                "type": "object",
                "properties": {"month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_product",
            "description": "المنتج (أو المنتجات) الأعلى مبيعًا حسب الكمية أو الإيراد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."},
                    "metric": {
                        "type": "string",
                        "enum": ["quantity", "revenue"],
                        "description": "أساس الترتيب: quantity أو revenue.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_lowest_product",
            "description": "المنتج (أو المنتجات) الأقل مبيعًا حسب الكمية أو الإيراد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."},
                    "metric": {
                        "type": "string",
                        "enum": ["quantity", "revenue"],
                        "description": "أساس الترتيب: quantity أو revenue.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "قارني بين منتجين أو أكتر (كمية وإيراد) لشهر محدد أو لكل الفترة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "أسماء المنتجات المطلوب مقارنتها.",
                    },
                    "month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."},
                },
                "required": ["product_names"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_transactions",
            "description": (
                "رجّعي صفوف transactions فعلية (تاريخ، كمية، سعر) - "
                "استخدميها بس لما المستخدم يطلب يشوف التفاصيل/الصفوف نفسها، "
                "مش للحساب. لو المستخدم حدد نطاق أيام دقيق (مش شهر كامل، "
                "مثلاً 'أول أسبوع من يوليو')، استخدمي date_from/date_to "
                "بدل month - هيك الجدول يطابق بالضبط النطاق يلي بتحكي عنه "
                "بجوابك، مش يرجع صفوف زيادة برا النطاق."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "month": {"type": "string", "description": "YYYY-MM - لشهر كامل بس."},
                    "date_from": {"type": "string", "description": "YYYY-MM-DD - لنطاق أيام دقيق."},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD - لنطاق أيام دقيق."},
                    "limit": {"type": "integer", "description": "افتراضي 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_number_of_orders",
            "description": "عدد الطلبات (orders) الفريدة لشهر محدد أو لكل الفترة.",
            "parameters": {
                "type": "object",
                "properties": {"month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_average_order_value",
            "description": "متوسط قيمة الطلب الواحد لشهر محدد أو لكل الفترة.",
            "parameters": {
                "type": "object",
                "properties": {"month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue_growth_rate",
            "description": "نسبة نمو الإيراد بين آخر شهرين فيهم بيانات (تلقائي - ما بتحتاج تحددي الشهور).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_growth_rate",
            "description": "نسبة نمو الكمية المباعة بين آخر شهرين فيهم بيانات (تلقائي).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_summary",
            "description": (
                "ملخص شامل لمنتج واحد: إجمالي الكمية والإيراد، عدد الطلبات، "
                "متوسط السعر، أول وآخر تاريخ بيع، وتفصيل شهري."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "month": {"type": "string", "description": "YYYY-MM أو فاضي لكل الفترة."},
                },
                "required": ["product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_breakdown",
            "description": (
                "تفصيل شهري (كمية وإيراد) عبر الوقت - لكل المنتجات أو لمنتج واحد. "
                "استخدميها لأسئلة الترند/التغير عبر الوقت."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "اختياري - اتركيه فاضي لكل المنتجات."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_date_range_summary",
            "description": "ملخص لفترة تاريخ حرة (مش لازم شهر كامل) - إيراد، كمية، عدد طلبات، أعلى منتج بالفترة.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["date_from", "date_to"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": "تفاصيل طلب واحد محدد (order_id): كل الأصناف فيه وإجماليه.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_data_overview",
            "description": (
                "نظرة عامة: شو الشهور والمنتجات المتوفرة بالداتا فعليًا، وأقدم/أحدث تاريخ. "
                "استخدميها أول ما ما تكوني متأكدة إذا شهر أو منتج مذكور بسؤال المستخدم موجود أصلاً بالداتا."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_sales",
            "description": (
                "استعلام عام مرن - استخدميه لأي سؤال ما بتغطيه الأدوات المسمّاة فوق: "
                "فلترة اختيارية بمنتج و/أو فترة تاريخ، مع تجميع اختياري (بمنتج/شهر/يوم) "
                "ومقياس (revenue/units/transaction_count)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                    "group_by": {
                        "type": "string",
                        "enum": ["none", "product", "month", "day"],
                        "description": "افتراضي none (رقم واحد إجمالي).",
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["revenue", "units", "transaction_count"],
                        "description": "افتراضي revenue.",
                    },
                },
            },
        },
    },
]

TOOL_DISPATCH = {
    "get_total_revenue": get_total_revenue,
    "get_total_units": get_total_units,
    "get_top_product": get_top_product,
    "get_lowest_product": get_lowest_product,
    "compare_products": compare_products,
    "list_transactions": list_transactions,
    "get_number_of_orders": get_number_of_orders,
    "get_average_order_value": get_average_order_value,
    "get_revenue_growth_rate": get_revenue_growth_rate,
    "get_sales_growth_rate": get_sales_growth_rate,
    "get_product_summary": get_product_summary,
    "get_monthly_breakdown": get_monthly_breakdown,
    "get_date_range_summary": get_date_range_summary,
    "get_order_details": get_order_details,
    "get_available_data_overview": get_available_data_overview,
    "query_sales": query_sales,
}
