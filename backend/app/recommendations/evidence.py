from __future__ import annotations

from app.anomaly.schemas import Anomaly
from app.data_pipeline.preparation import load_cleaned
from app.recommendations.contract import Evidence


def calculate_units_lost(anomaly: Anomaly) -> float | None:
    """Calculate missing units relative to the baseline."""

    if anomaly.baseline_value is None:
        return None

    if anomaly.current_value >= anomaly.baseline_value:
        return None

    return anomaly.baseline_value - anomaly.current_value


def build_evidence(
    anomaly: Anomaly,
    user_id: int,
    filename: str,
) -> Evidence:
    df = load_cleaned(user_id, filename)

    units_lost = calculate_units_lost(anomaly)

    revenue_at_risk = None
    revenue_share_percent = None

    if "revenue" not in df.columns:
        df = df.copy()
        df["revenue"] = df["quantity"].astype(float) * df["unit_price"].astype(float)

    total_revenue = float(df["revenue"].sum())

    if anomaly.product_id:
        product_rows = df[df["product_id"].astype(str) == str(anomaly.product_id)]

        if not product_rows.empty:
            product_revenue = float(product_rows["revenue"].sum())

            average_unit_price = float(product_rows["unit_price"].mean())

            if units_lost is not None:
                revenue_at_risk = units_lost * average_unit_price

            if total_revenue > 0:
                revenue_share_percent = (product_revenue / total_revenue) * 100

    return Evidence(
        metric=anomaly.metric,
        current_value=anomaly.current_value,
        baseline_value=anomaly.baseline_value,
        change_percent=anomaly.change_percent,
        units_lost=units_lost,
        revenue_at_risk=revenue_at_risk,
        revenue_share_percent=revenue_share_percent,
        period_start=anomaly.period_start,
        period_end=anomaly.period_end,
        currency=None,
    )
