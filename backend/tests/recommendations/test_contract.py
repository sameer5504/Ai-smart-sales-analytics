"""Invariants of the recommendation contract and its fixtures.

While these pass, either side of the feature can be built against the
fixtures without the other side existing.
"""

import pandas as pd
import pytest
from pydantic import ValidationError

from app.anomaly.schemas import AnomalySeverity
from app.recommendations.contract import (
    DEFAULT_MAX_RECOMMENDATIONS,
    REASON_NO_FINDINGS,
    STATUS_AVAILABLE,
    STATUS_UNAVAILABLE,
    Impact,
    ImpactConfidence,
    RecommendationsResult,
)
from app.recommendations.demand import (
    UNAVAILABLE,
    DemandEstimate,
    build_demand_estimates,
    lookup,
)
from tests.fixtures import anomalies, recommendations


def test_every_fixture_recommendation_answers_a_real_finding():
    known = {a.message for a in anomalies.ALL_ANOMALIES}

    for rec in recommendations.ALL_RECOMMENDATIONS:
        assert rec.finding.message in known


def test_every_recommendation_has_an_action_and_a_rationale():
    """US-4.3.1: a finding without an action is only half the feature."""
    for rec in recommendations.ALL_RECOMMENDATIONS:
        assert rec.action.strip()
        assert rec.rationale.strip()


def test_every_recommendation_has_quantified_evidence():
    """US-4.3.2."""
    for rec in recommendations.ALL_RECOMMENDATIONS:
        assert rec.evidence.metric
        assert rec.evidence.current_value is not None
        assert rec.evidence.period_start <= rec.evidence.period_end


def test_every_impact_is_labelled_measured_or_projected():
    """US-4.3.3 and US-5.4.3: the assistant states which one it is."""
    for rec in recommendations.ALL_RECOMMENDATIONS:
        impact = rec.expected_impact
        assert impact.confidence in set(ImpactConfidence)
        assert impact.basis.strip()

        if impact.value is None:
            assert impact.unavailable_reason, f"{rec.id} has no impact value and no reason why"


def test_impact_requires_a_basis():
    with pytest.raises(ValidationError):
        Impact(value=100.0, currency="GBP", basis="")


def test_severity_comes_from_the_finding():
    assert recommendations.COFFEE_DROP.severity is AnomalySeverity.CRITICAL
    assert recommendations.COFFEE_DROP.is_critical
    assert not recommendations.DATES_INCREASE.is_critical


def test_evidence_period_matches_its_finding():
    for rec in recommendations.ALL_RECOMMENDATIONS:
        assert rec.evidence.period_start == rec.finding.period_start
        assert rec.evidence.period_end == rec.finding.period_end


def test_available_result_reports_what_it_held_back():
    """US-4.3.6."""
    result = recommendations.capped_result()

    assert result.status == STATUS_AVAILABLE
    assert len(result.recommendations) <= DEFAULT_MAX_RECOMMENDATIONS
    assert result.suppressed_count == result.total_findings - len(result.recommendations)


def test_unavailable_result_for_no_findings():
    result = recommendations.empty_result()

    assert result.status == STATUS_UNAVAILABLE
    assert result.reason == REASON_NO_FINDINGS
    assert result.message
    assert result.recommendations == []


def test_critical_returns_only_critical_recommendations():
    """US-5.8.3."""
    result = recommendations.available_result()

    assert recommendations.COFFEE_DROP in result.critical
    assert recommendations.DATES_INCREASE not in result.critical


def test_result_serialises_to_the_documented_shape():
    payload = recommendations.available_result().model_dump(mode="json")

    assert payload["status"] == STATUS_AVAILABLE
    assert payload["generated_at"]

    first = payload["recommendations"][0]
    assert {
        "id",
        "finding",
        "action",
        "rationale",
        "evidence",
        "expected_impact",
    } <= set(first)
    assert first["finding"]["anomaly_type"] == "sharp_drop"
    assert first["expected_impact"]["confidence"] in {"measured", "projected"}


def test_unavailable_result_keeps_a_message():
    payload = RecommendationsResult.unavailable(
        reason=REASON_NO_FINDINGS,
        message="Nothing unusual turned up.",
    ).model_dump(mode="json")

    assert payload["recommendations"] == []
    assert payload["message"]


def test_build_demand_estimates_returns_something_for_every_product():
    """The rules are handed a mapping whether or not a forecast exists.

    The forecast lands separately, so on main this exercises the fallback.
    What the forecast adds is covered in test_demand_forecast.py.
    """
    rows = pd.DataFrame(
        [
            ("2026-04-10", "P001", 10.0),
            ("2026-05-10", "P001", 10.0),
            ("2026-06-30", "P001", 10.0),
        ],
        columns=["transaction_date", "product_id", "quantity"],
    )

    estimates = build_demand_estimates(rows)

    assert estimates["P001"].is_available
    assert estimates["P001"].source is not None


def test_lookup_returns_an_unavailable_estimate_for_an_unknown_product():
    """A product the forecast did not cover must not raise."""
    estimator = lookup({"P001": DemandEstimate(expected_units=130.0)})

    assert estimator("P001").expected_units == 130.0
    assert estimator("P999") is UNAVAILABLE
    assert not estimator("P999").is_available


def test_demand_estimate_reports_its_own_absence():
    estimate = DemandEstimate(unavailable_reason="insufficient_history")

    assert not estimate.is_available
    assert estimate.expected_units is None
