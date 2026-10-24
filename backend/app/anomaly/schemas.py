"""Schemas for anomalies produced by detection and read by recommendations.

Detection (US-4.1.x) builds these objects and recommendation generation
(US-4.3.x) consumes them. The shape is fixed ahead of both implementations so
they can be developed in parallel against tests/fixtures/anomalies.py.

Three fields carry three separate facts, and none of them repeats another:

    anomaly_type  what shape of change happened
    scope         who it happened to, the store or one product
    metric        what was measured, units or revenue

A store revenue drop is SHARP_DROP with scope=store and metric=revenue. A
product running out of sales is DEAD_STOCK with scope=product. Adding a metric
or a scope therefore does not add anomaly types.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnomalyType(StrEnum):
    """The shape of the detected change, independent of scope and metric."""

    SHARP_DROP = "sharp_drop"
    UNUSUAL_INCREASE = "unusual_increase"
    DEAD_STOCK = "dead_stock"


class AnomalyScope(StrEnum):
    """Whether the finding is about the whole business or a single product."""

    STORE = "store"
    PRODUCT = "product"


class AnomalyMetric(StrEnum):
    """What was measured.

    Units and revenue move independently: fewer units at a higher price can
    raise revenue while sales fall, so US-4.1.1 needs both watched separately.
    """

    UNITS_SOLD = "units_sold"
    REVENUE = "revenue"


class AnomalySeverity(StrEnum):
    """How urgently the finding needs attention (US-4.1.6)."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


# Sort key for ranking, most urgent first. Sorting on the string value would
# order alphabetically, which puts critical before info before warning.
SEVERITY_RANK: dict[str, int] = {
    AnomalySeverity.CRITICAL: 0,
    AnomalySeverity.WARNING: 1,
    AnomalySeverity.INFO: 2,
}


class Anomaly(BaseModel):
    """One abnormal change detected in a business's sales data.

    Frozen, so anything that adds to a finding wraps it in a Recommendation
    rather than modifying it.

    Attributes:
        anomaly_type: the shape of the change.
        scope: store level or product level.
        metric: units sold or revenue.
        severity: how urgently it needs attention.
        product_id: the product, for product-scope findings. None for store.
        product_name: display name, when the upload carried one.
        category: the product's category, when the column was mapped. Used by
            the category-aware tailoring in US-4.3.4.
        period_start: first day of the evaluated window.
        period_end: last day of the evaluated window.
        current_value: the metric's value in the evaluated period.
        baseline_value: the normal value from the business's own history.
            None for rules that use no baseline, such as dead stock.
        change_percent: signed percentage change against the baseline. None
            when there is no baseline.
        message: plain description of what was detected, safe to show as is.
    """

    model_config = ConfigDict(frozen=True)

    anomaly_type: AnomalyType
    scope: AnomalyScope
    metric: AnomalyMetric
    severity: AnomalySeverity

    product_id: str | None = None
    product_name: str | None = None
    category: str | None = None

    period_start: date
    period_end: date

    current_value: float
    baseline_value: float | None = None
    change_percent: float | None = None

    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_scope_matches_product(self) -> Anomaly:
        """Product findings name a product, store findings do not."""
        if self.scope is AnomalyScope.PRODUCT and not self.product_id:
            raise ValueError("A product-scope anomaly requires a product_id.")
        if self.scope is AnomalyScope.STORE and self.product_id:
            raise ValueError("A store-scope anomaly must not name a product.")
        return self

    @model_validator(mode="after")
    def _check_dead_stock_is_product_scoped(self) -> Anomaly:
        """Dead stock describes one product that stopped selling."""
        if self.anomaly_type is AnomalyType.DEAD_STOCK and self.scope is not AnomalyScope.PRODUCT:
            raise ValueError("Dead stock is only meaningful for a product.")
        return self

    @model_validator(mode="after")
    def _check_period_order(self) -> Anomaly:
        """The evaluated window runs forwards."""
        if self.period_end < self.period_start:
            raise ValueError("period_end cannot be before period_start.")
        return self

    @property
    def severity_rank(self) -> int:
        """Sort key for ranking. Lower is more urgent."""
        return SEVERITY_RANK[self.severity]

    @property
    def subject(self) -> str:
        """What the finding is about, for messages and de-duplication.

        A product-scope anomaly always has a product_id, enforced by
        _check_scope_matches_product.
        """
        if self.scope is AnomalyScope.STORE:
            return "store"
        return self.product_name or self.product_id

    @property
    def dedupe_key(self) -> tuple:
        """Identifies the underlying event, ignoring which metric saw it.

        Units and revenue can both fall in the same period, producing two
        findings for one event. Ranking groups on this key so the business
        owner is told about it once (US-4.3.6).
        """
        return (self.scope, self.subject, self.anomaly_type, self.period_start)
