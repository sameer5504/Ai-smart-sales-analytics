from app.recommendations.contract import Evidence
from app.recommendations.service import (
    build_recommendation_id,
    generate_recommendation,
    generate_recommendations,
)
from tests.fixtures import anomalies


def _fake_evidence(anomaly):
    return Evidence(
        metric=anomaly.metric,
        current_value=anomaly.current_value,
        baseline_value=anomaly.baseline_value,
        change_percent=anomaly.change_percent,
        units_lost=None,
        revenue_at_risk=None,
        revenue_share_percent=None,
        period_start=anomaly.period_start,
        period_end=anomaly.period_end,
        currency=None,
    )


def test_build_recommendation_id_is_stable():
    recommendation_id = build_recommendation_id(anomalies.SHARP_DROP)

    assert recommendation_id.startswith("rec-")


def test_generate_recommendation_returns_a_recommendation(monkeypatch):
    monkeypatch.setattr(
        "app.recommendations.service.build_evidence",
        lambda anomaly, user_id, filename: _fake_evidence(anomaly),
    )

    recommendation = generate_recommendation(
        anomalies.SHARP_DROP,
        1,
        "test.csv",
    )

    assert recommendation.finding == anomalies.SHARP_DROP
    assert recommendation.action
    assert recommendation.rationale


def test_generate_recommendations_are_ranked(monkeypatch):
    monkeypatch.setattr(
        "app.recommendations.service.build_evidence",
        lambda anomaly, user_id, filename: _fake_evidence(anomaly),
    )

    recommendations = generate_recommendations(
        anomalies.ALL_ANOMALIES,
        1,
        "test.csv",
    )

    assert recommendations


def test_generate_recommendations_are_limited(monkeypatch):
    monkeypatch.setattr(
        "app.recommendations.service.build_evidence",
        lambda anomaly, user_id, filename: _fake_evidence(anomaly),
    )

    recommendations = generate_recommendations(
        anomalies.many_anomalies(20),
        1,
        "test.csv",
    )

    assert len(recommendations) <= 5
