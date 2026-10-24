"""Sample recommendations matching the anomalies in anomalies.py.

Used in place of the engine (US-4.3.x) so the endpoint, the chatbot grounding
and the dashboard entry point can be built and tested before any rule exists.
The figures are ones the engine will really compute, so tests written against
these keep passing when the real engine replaces them.
"""

from __future__ import annotations

from app.anomaly.schemas import AnomalyMetric
from app.recommendations.contract import (
    DEFAULT_MAX_RECOMMENDATIONS,
    REASON_NO_FINDINGS,
    DemandSource,
    Evidence,
    Impact,
    ImpactConfidence,
    Recommendation,
    RecommendationsResult,
)
from tests.fixtures import anomalies

CURRENCY = "GBP"


COFFEE_DROP = Recommendation(
    id="rec-p001-sharp-drop",
    finding=anomalies.SHARP_DROP,
    action=("Check Coffee 250g for a stock gap or a price change, and restock to about 130 units for next month."),
    rationale=(
        "Coffee 250g is your largest product by revenue and it sold 65% below "
        "its usual weekly volume. A drop that size on a product this important "
        "moves the whole month's total."
    ),
    evidence=Evidence(
        metric=AnomalyMetric.UNITS_SOLD,
        current_value=42.0,
        baseline_value=120.0,
        change_percent=-65.0,
        units_lost=78.0,
        revenue_at_risk=3510.0,
        revenue_share_percent=22.4,
        period_start=anomalies.PERIOD_START,
        period_end=anomalies.PERIOD_END,
        currency=CURRENCY,
    ),
    expected_impact=Impact(
        value=3510.0,
        currency=CURRENCY,
        confidence=ImpactConfidence.PROJECTED,
        basis="if weekly sales return to the four-week median of 120 units",
    ),
    priority=1,
    restock_units=130.0,
    demand_source=DemandSource.PRODUCT_FORECAST,
)

STORE_DROP = Recommendation(
    id="rec-store-revenue-drop",
    finding=anomalies.STORE_REVENUE_DROP,
    action=(
        "Review July against the three months before it, starting with the two products whose sales fell furthest."
    ),
    rationale=(
        "Total revenue fell about a third against the preceding three-month "
        "average. That is a whole-business change rather than one product "
        "having a bad month."
    ),
    evidence=Evidence(
        metric=AnomalyMetric.REVENUE,
        current_value=18400.0,
        baseline_value=27300.0,
        change_percent=-32.6,
        units_lost=None,
        revenue_at_risk=8900.0,
        revenue_share_percent=None,
        period_start=anomalies.MONTH_START,
        period_end=anomalies.MONTH_END,
        currency=CURRENCY,
    ),
    expected_impact=Impact(
        value=8900.0,
        currency=CURRENCY,
        confidence=ImpactConfidence.MEASURED,
        basis="the shortfall against the preceding three-month average",
    ),
    priority=2,
)

SUMAC_DEAD_STOCK = Recommendation(
    id="rec-p006-dead-stock",
    finding=anomalies.DEAD_STOCK,
    action=(
        "Discount Sumac 200g to clear it, or move it somewhere more visible before the stock ties up any more cash."
    ),
    rationale=(
        "Sumac 200g has sold nothing for four trading weeks after selling "
        "steadily before that, which usually means placement or a price "
        "problem rather than lost demand."
    ),
    evidence=Evidence(
        metric=AnomalyMetric.UNITS_SOLD,
        current_value=0.0,
        baseline_value=None,
        change_percent=None,
        units_lost=None,
        revenue_at_risk=216.0,
        revenue_share_percent=0.4,
        period_start=anomalies.PERIOD_START,
        period_end=anomalies.PERIOD_END,
        currency=CURRENCY,
    ),
    expected_impact=Impact(
        value=216.0,
        currency=CURRENCY,
        confidence=ImpactConfidence.PROJECTED,
        basis="the value of the unsold stock at its last selling price",
    ),
    priority=3,
)

DATES_INCREASE = Recommendation(
    id="rec-p002-unusual-increase",
    finding=anomalies.UNUSUAL_INCREASE,
    action=("Find out what drove Dates 1kg to more than double, and keep stock above 300 units while it lasts."),
    rationale=(
        "Dates 1kg sold 121% above its usual weekly volume. Worth understanding "
        "so it can be repeated, and worth stocking for so the run is not cut "
        "short by an empty shelf."
    ),
    evidence=Evidence(
        metric=AnomalyMetric.UNITS_SOLD,
        current_value=310.0,
        baseline_value=140.0,
        change_percent=121.4,
        units_lost=None,
        revenue_at_risk=None,
        revenue_share_percent=15.1,
        period_start=anomalies.PERIOD_START,
        period_end=anomalies.PERIOD_END,
        currency=CURRENCY,
    ),
    expected_impact=Impact(
        value=None,
        currency=CURRENCY,
        confidence=ImpactConfidence.PROJECTED,
        basis="no reliable estimate: the increase has only one week of history",
        unavailable_reason="insufficient_history",
    ),
    priority=4,
    restock_units=320.0,
    demand_source=DemandSource.TRAILING_SALES,
)


ALL_RECOMMENDATIONS: list[Recommendation] = [
    COFFEE_DROP,
    STORE_DROP,
    SUMAC_DEAD_STOCK,
    DATES_INCREASE,
]


def available_result(
    recommendations: list[Recommendation] | None = None,
    *,
    total_findings: int = len(anomalies.ALL_ANOMALIES),
) -> RecommendationsResult:
    """A populated result for the endpoint and the chatbot to render."""
    items = ALL_RECOMMENDATIONS if recommendations is None else recommendations
    suppressed = max(0, total_findings - len(items))

    return RecommendationsResult.available(
        recommendations=items,
        total_findings=total_findings,
        suppressed_count=suppressed,
    )


def capped_result() -> RecommendationsResult:
    """A result at the cap, with findings held back (US-4.3.6)."""
    total = 20
    return RecommendationsResult.available(
        recommendations=ALL_RECOMMENDATIONS[:DEFAULT_MAX_RECOMMENDATIONS],
        total_findings=total,
        suppressed_count=total - len(ALL_RECOMMENDATIONS[:DEFAULT_MAX_RECOMMENDATIONS]),
    )


def empty_result() -> RecommendationsResult:
    """Nothing to report, which is a normal outcome rather than an error."""
    return RecommendationsResult.unavailable(
        reason=REASON_NO_FINDINGS,
        message="Nothing unusual turned up in this data. Your numbers look steady.",
    )
