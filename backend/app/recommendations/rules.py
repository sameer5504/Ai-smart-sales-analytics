from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.anomaly.schemas import (
    Anomaly,
    AnomalyMetric,
    AnomalyScope,
    AnomalyType,
)


@dataclass(frozen=True)
class RuleResult:
    """Output produced by a recommendation rule."""

    action: str
    rationale: str


def category_action(
    category: str | None,
    default_action: str,
) -> str:
    if not category:
        return default_action

    category = category.lower()

    if "elect" in category:
        return "Review competitor pricing, inventory levels, and product lifecycle."

    if any(word in category for word in ["food", "drink", "beverage"]):
        return "Review freshness, expiry cycles, and promotional activity."

    if any(word in category for word in ["cloth", "fashion", "apparel"]):
        return "Review seasonal demand and inventory levels."

    return default_action


def product_sharp_drop_rule(anomaly: Anomaly) -> RuleResult:
    return RuleResult(
        action=category_action(
            anomaly.category,
            (f"Check stock availability and recent pricing changes for {anomaly.subject}."),
        ),
        rationale=(f"{anomaly.subject} is performing significantly below its normal baseline."),
    )


def store_unusual_increase_rule(anomaly: Anomaly) -> RuleResult:
    return RuleResult(
        action="Identify the factors behind the improvement and maintain them.",
        rationale="Store performance is significantly above its historical baseline.",
    )


def dead_stock_rule(anomaly: Anomaly) -> RuleResult:
    return RuleResult(
        action=category_action(
            anomaly.category,
            (f"Discount {anomaly.subject} or improve its visibility to restore demand."),
        ),
        rationale=(f"{anomaly.subject} has generated no sales during the evaluation period."),
    )


def store_sharp_drop_rule(anomaly: Anomaly) -> RuleResult:
    if anomaly.metric is AnomalyMetric.REVENUE:
        return RuleResult(
            action="Review declining products and investigate revenue drivers.",
            rationale="Store revenue is significantly below its historical baseline.",
        )

    return RuleResult(
        action="Review product availability and customer demand across the business.",
        rationale="Store unit sales are significantly below normal levels.",
    )


def product_unusual_increase_rule(anomaly: Anomaly) -> RuleResult:
    return RuleResult(
        action=category_action(
            anomaly.category,
            (f"Maintain adequate inventory for {anomaly.subject} and investigate the cause of the increase."),
        ),
        rationale=(f"{anomaly.subject} is performing significantly above its normal baseline."),
    )


def fallback_rule(_: Anomaly) -> RuleResult:
    return RuleResult(
        action="Review this finding and investigate the underlying cause.",
        rationale="No specialised recommendation rule is available.",
    )


RuleFunction = Callable[[Anomaly], RuleResult]


RULE_REGISTRY: dict[tuple[AnomalyType, AnomalyScope], RuleFunction] = {
    (AnomalyType.SHARP_DROP, AnomalyScope.PRODUCT): product_sharp_drop_rule,
    (AnomalyType.DEAD_STOCK, AnomalyScope.PRODUCT): dead_stock_rule,
    (AnomalyType.UNUSUAL_INCREASE, AnomalyScope.PRODUCT): product_unusual_increase_rule,
    (AnomalyType.SHARP_DROP, AnomalyScope.STORE): store_sharp_drop_rule,
    (AnomalyType.UNUSUAL_INCREASE, AnomalyScope.STORE): store_unusual_increase_rule,
}


def get_rule(anomaly: Anomaly) -> RuleFunction:
    """Return the matching rule or the fallback."""

    return RULE_REGISTRY.get(
        (anomaly.anomaly_type, anomaly.scope),
        fallback_rule,
    )
