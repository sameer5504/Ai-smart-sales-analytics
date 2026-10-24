from __future__ import annotations

from app.anomaly.schemas import Anomaly
from app.recommendations.contract import (
    DEFAULT_MAX_RECOMMENDATIONS,
    Evidence,
    Impact,
    ImpactConfidence,
    Recommendation,
)
from app.recommendations.evidence import build_evidence
from app.recommendations.rules import get_rule


def build_recommendation_id(anomaly: Anomaly) -> str:
    """Build a stable recommendation identifier."""

    return f"rec-{anomaly.scope.value}-{anomaly.anomaly_type.value}-{anomaly.subject}"


def generate_recommendation(
    anomaly: Anomaly,
    user_id: int,
    filename: str,
    demand_estimates: dict | None = None,
) -> Recommendation:
    evidence = build_evidence(anomaly, user_id, filename)

    result = get_rule(anomaly)(anomaly)

    restock_units = None
    demand_source = None

    if demand_estimates and anomaly.product_id:
        estimate = demand_estimates.get(str(anomaly.product_id))

        if estimate and estimate.is_available:
            restock_units = estimate.expected_units
            demand_source = estimate.source

    return Recommendation(
        id=build_recommendation_id(anomaly),
        finding=anomaly,
        action=result.action,
        rationale=result.rationale,
        evidence=evidence,
        expected_impact=estimate_impact(evidence),
        restock_units=restock_units,
        demand_source=demand_source,
    )


def generate_recommendations(
    anomalies: list[Anomaly],
    user_id: int,
    filename: str,
    demand_estimates: dict | None = None,
) -> tuple[list[Recommendation], int]:
    recommendations = [
        generate_recommendation(
            anomaly,
            user_id,
            filename,
            demand_estimates,
        )
        for anomaly in anomalies
    ]

    unique_recommendations = {}

    for recommendation in recommendations:
        unique_recommendations[recommendation.finding.dedupe_key] = recommendation

    recommendations = list(unique_recommendations.values())

    recommendations.sort(
        key=lambda recommendation: (
            recommendation.finding.severity_rank,
            -(recommendation.expected_impact.value or 0),
        )
    )

    ranked_recommendations = []

    for priority, recommendation in enumerate(
        recommendations,
        start=1,
    ):
        ranked_recommendations.append(
            recommendation.model_copy(
                update={
                    "priority": priority,
                },
            )
        )

    limited_recommendations = ranked_recommendations[:DEFAULT_MAX_RECOMMENDATIONS]

    suppressed_count = max(
        len(ranked_recommendations) - len(limited_recommendations),
        0,
    )

    return (
        limited_recommendations,
        suppressed_count,
    )


def estimate_impact(evidence: Evidence) -> Impact:
    if evidence.revenue_at_risk is None:
        return Impact(
            value=None,
            currency=None,
            confidence=ImpactConfidence.PROJECTED,
            basis="Insufficient evidence to estimate impact.",
            unavailable_reason="insufficient_data",
        )

    return Impact(
        value=evidence.revenue_at_risk,
        currency=None,
        confidence=ImpactConfidence.PROJECTED,
        basis="Estimated from revenue at risk identified in the anomaly.",
    )
