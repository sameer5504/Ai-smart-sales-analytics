"""Sample anomalies covering every type and severity.

Used in place of detection (US-4.1.x) until it is merged, so recommendation
work can be built and tested now. The figures are internally consistent: a
drop's current_value really is the stated percentage below its baseline, and
tests/anomaly/test_schemas.py checks that.

The sample business is a small speciality grocer, matching the files under
pr-samples/.
"""

from __future__ import annotations

from datetime import date

from app.anomaly.schemas import (
    Anomaly,
    AnomalyMetric,
    AnomalyScope,
    AnomalySeverity,
    AnomalyType,
)

# Evaluation window for the product-level fixtures.
PERIOD_START = date(2026, 7, 20)
PERIOD_END = date(2026, 7, 26)

# Evaluation window for the store-level fixtures.
MONTH_START = date(2026, 7, 1)
MONTH_END = date(2026, 7, 31)


SHARP_DROP = Anomaly(
    anomaly_type=AnomalyType.SHARP_DROP,
    scope=AnomalyScope.PRODUCT,
    severity=AnomalySeverity.CRITICAL,
    product_id="P001",
    product_name="Coffee 250g",
    category="beverages",
    metric=AnomalyMetric.UNITS_SOLD,
    period_start=PERIOD_START,
    period_end=PERIOD_END,
    current_value=42.0,
    baseline_value=120.0,
    change_percent=-65.0,
    message="Coffee 250g sold 42 units this week, 65% below its four-week median of 120.",
)

# Same rule with a milder change, so severity is not tied to the type.
SHARP_DROP_WARNING = Anomaly(
    anomaly_type=AnomalyType.SHARP_DROP,
    scope=AnomalyScope.PRODUCT,
    severity=AnomalySeverity.WARNING,
    product_id="P004",
    product_name="Honey 500g",
    category="pantry",
    metric=AnomalyMetric.UNITS_SOLD,
    period_start=PERIOD_START,
    period_end=PERIOD_END,
    current_value=28.0,
    baseline_value=56.0,
    change_percent=-50.0,
    message="Honey 500g sold 28 units this week, 50% below its four-week median of 56.",
)

DEAD_STOCK = Anomaly(
    anomaly_type=AnomalyType.DEAD_STOCK,
    scope=AnomalyScope.PRODUCT,
    severity=AnomalySeverity.WARNING,
    product_id="P006",
    product_name="Sumac 200g",
    category="spices",
    metric=AnomalyMetric.UNITS_SOLD,
    period_start=PERIOD_START,
    period_end=PERIOD_END,
    current_value=0.0,
    baseline_value=None,
    change_percent=None,
    message="Sumac 200g has sold nothing for four consecutive trading weeks.",
)

UNUSUAL_INCREASE = Anomaly(
    anomaly_type=AnomalyType.UNUSUAL_INCREASE,
    scope=AnomalyScope.PRODUCT,
    severity=AnomalySeverity.INFO,
    product_id="P002",
    product_name="Dates 1kg",
    category="produce",
    metric=AnomalyMetric.UNITS_SOLD,
    period_start=PERIOD_START,
    period_end=PERIOD_END,
    current_value=310.0,
    baseline_value=140.0,
    change_percent=121.4,
    message="Dates 1kg sold 310 units this week, more than double its four-week median of 140.",
)

# No category, for testing the fallback when the column was not mapped.
UNCATEGORISED_DROP = Anomaly(
    anomaly_type=AnomalyType.SHARP_DROP,
    scope=AnomalyScope.PRODUCT,
    severity=AnomalySeverity.WARNING,
    product_id="P009",
    product_name="Gift Box",
    category=None,
    metric=AnomalyMetric.UNITS_SOLD,
    period_start=PERIOD_START,
    period_end=PERIOD_END,
    current_value=9.0,
    baseline_value=30.0,
    change_percent=-70.0,
    message="Gift Box sold 9 units this week, 70% below its four-week median of 30.",
)

STORE_REVENUE_DROP = Anomaly(
    anomaly_type=AnomalyType.SHARP_DROP,
    scope=AnomalyScope.STORE,
    severity=AnomalySeverity.CRITICAL,
    metric=AnomalyMetric.REVENUE,
    period_start=MONTH_START,
    period_end=MONTH_END,
    current_value=18400.0,
    baseline_value=27300.0,
    change_percent=-32.6,
    message="Total revenue for July was 18,400, about a third below the preceding three-month average.",
)

STORE_REVENUE_SPIKE = Anomaly(
    anomaly_type=AnomalyType.UNUSUAL_INCREASE,
    scope=AnomalyScope.STORE,
    severity=AnomalySeverity.INFO,
    metric=AnomalyMetric.REVENUE,
    period_start=MONTH_START,
    period_end=MONTH_END,
    current_value=41200.0,
    baseline_value=27300.0,
    change_percent=50.9,
    message="Total revenue for July was 41,200, about half again above the preceding three-month average.",
)


# Units fell while revenue rose, because the same period sold fewer items at a
# higher price. A revenue-only detector misses this entirely (US-4.1.1).
STORE_UNITS_DROP = Anomaly(
    anomaly_type=AnomalyType.SHARP_DROP,
    scope=AnomalyScope.STORE,
    metric=AnomalyMetric.UNITS_SOLD,
    severity=AnomalySeverity.WARNING,
    period_start=MONTH_START,
    period_end=MONTH_END,
    current_value=1420.0,
    baseline_value=2840.0,
    change_percent=-50.0,
    message="The business sold 1,420 units in July, half its recent monthly average of 2,840.",
)
# One of every type, for tests that cover the whole dispatch table.
ALL_ANOMALIES: list[Anomaly] = [
    SHARP_DROP,
    SHARP_DROP_WARNING,
    DEAD_STOCK,
    UNUSUAL_INCREASE,
    UNCATEGORISED_DROP,
    STORE_REVENUE_DROP,
    STORE_UNITS_DROP,
    STORE_REVENUE_SPIKE,
]

PRODUCT_ANOMALIES: list[Anomaly] = [a for a in ALL_ANOMALIES if a.scope is AnomalyScope.PRODUCT]

STORE_ANOMALIES: list[Anomaly] = [a for a in ALL_ANOMALIES if a.scope is AnomalyScope.STORE]


def many_anomalies(count: int = 20) -> list[Anomaly]:
    """Return count distinct product anomalies, for testing the cap.

    Severities cycle so that input order alone does not produce a correct
    ranking (US-4.3.6).
    """
    severities = [
        AnomalySeverity.INFO,
        AnomalySeverity.CRITICAL,
        AnomalySeverity.WARNING,
    ]

    return [
        Anomaly(
            anomaly_type=AnomalyType.SHARP_DROP,
            scope=AnomalyScope.PRODUCT,
            severity=severities[index % len(severities)],
            product_id=f"P{index:03d}",
            product_name=f"Product {index}",
            category="pantry",
            metric=AnomalyMetric.UNITS_SOLD,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            current_value=float(50 - index),
            baseline_value=100.0,
            change_percent=-float(50 + index),
            message=f"Product {index} sold {50 - index} units this week, below its median of 100.",
        )
        for index in range(count)
    ]
