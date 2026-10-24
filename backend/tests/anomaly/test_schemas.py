"""Invariants of the anomaly contract."""

import pytest
from pydantic import ValidationError

from app.anomaly.schemas import (
    SEVERITY_RANK,
    Anomaly,
    AnomalyMetric,
    AnomalyScope,
    AnomalySeverity,
    AnomalyType,
)
from tests.fixtures import anomalies


def test_every_anomaly_type_has_a_fixture():
    covered = {a.anomaly_type for a in anomalies.ALL_ANOMALIES}
    assert covered == set(AnomalyType)


def test_every_metric_has_a_fixture():
    """US-4.1.1 watches units and revenue, so both must be exercised."""
    covered = {a.metric for a in anomalies.ALL_ANOMALIES}
    assert covered == set(AnomalyMetric)


def test_units_and_revenue_are_detected_independently():
    """A store can lose units while revenue rises, and both are findings."""
    units = anomalies.STORE_UNITS_DROP
    revenue = anomalies.STORE_REVENUE_DROP

    assert units.metric is AnomalyMetric.UNITS_SOLD
    assert revenue.metric is AnomalyMetric.REVENUE
    assert units.anomaly_type is revenue.anomaly_type
    assert units.scope is revenue.scope


def test_a_units_and_a_revenue_finding_share_a_dedupe_key():
    """One event seen twice collapses to one recommendation (US-4.3.6)."""
    assert anomalies.STORE_UNITS_DROP.dedupe_key == anomalies.STORE_REVENUE_DROP.dedupe_key


def test_different_products_do_not_share_a_dedupe_key():
    assert anomalies.SHARP_DROP.dedupe_key != anomalies.SHARP_DROP_WARNING.dedupe_key


def test_dead_stock_must_be_product_scoped():
    with pytest.raises(ValidationError, match="only meaningful for a product"):
        Anomaly(
            anomaly_type=AnomalyType.DEAD_STOCK,
            scope=AnomalyScope.STORE,
            metric=AnomalyMetric.UNITS_SOLD,
            severity=AnomalySeverity.WARNING,
            period_start=anomalies.MONTH_START,
            period_end=anomalies.MONTH_END,
            current_value=0.0,
            message="Store-wide dead stock is not a thing.",
        )


def test_every_severity_has_a_fixture():
    covered = {a.severity for a in anomalies.ALL_ANOMALIES}
    assert covered == set(AnomalySeverity)


def test_product_anomaly_requires_a_product_id():
    with pytest.raises(ValidationError, match="requires a product_id"):
        Anomaly(
            anomaly_type=AnomalyType.SHARP_DROP,
            scope=AnomalyScope.PRODUCT,
            severity=AnomalySeverity.WARNING,
            metric=AnomalyMetric.UNITS_SOLD,
            period_start=anomalies.PERIOD_START,
            period_end=anomalies.PERIOD_END,
            current_value=1.0,
            message="No product named.",
        )


def test_store_anomaly_rejects_a_product_id():
    with pytest.raises(ValidationError, match="must not name a product"):
        Anomaly(
            anomaly_type=AnomalyType.SHARP_DROP,
            scope=AnomalyScope.STORE,
            severity=AnomalySeverity.WARNING,
            product_id="P001",
            metric=AnomalyMetric.REVENUE,
            period_start=anomalies.MONTH_START,
            period_end=anomalies.MONTH_END,
            current_value=1.0,
            message="Store finding with a product attached.",
        )


def test_period_must_run_forwards():
    with pytest.raises(ValidationError, match="cannot be before"):
        Anomaly(
            anomaly_type=AnomalyType.SHARP_DROP,
            scope=AnomalyScope.STORE,
            severity=AnomalySeverity.INFO,
            metric=AnomalyMetric.REVENUE,
            period_start=anomalies.MONTH_END,
            period_end=anomalies.MONTH_START,
            current_value=1.0,
            message="Backwards period.",
        )


def test_anomaly_is_immutable():
    with pytest.raises(ValidationError):
        anomalies.SHARP_DROP.severity = AnomalySeverity.INFO


def test_severity_rank_orders_most_urgent_first():
    assert (
        SEVERITY_RANK[AnomalySeverity.CRITICAL]
        < SEVERITY_RANK[AnomalySeverity.WARNING]
        < SEVERITY_RANK[AnomalySeverity.INFO]
    )


def test_subject_names_the_product_or_the_store():
    assert anomalies.SHARP_DROP.subject == "Coffee 250g"
    assert anomalies.STORE_REVENUE_DROP.subject == "store"


def test_fixture_change_percent_matches_its_values():
    """Rules compute from these figures, so they have to be consistent."""
    for anomaly in anomalies.ALL_ANOMALIES:
        if anomaly.baseline_value in (None, 0) or anomaly.change_percent is None:
            continue

        expected = (anomaly.current_value - anomaly.baseline_value) / anomaly.baseline_value * 100
        assert anomaly.change_percent == pytest.approx(expected, abs=0.6), (
            f"{anomaly.product_id or 'store'} states {anomaly.change_percent}% but its values imply {expected:.1f}%"
        )


def test_many_anomalies_are_distinct_and_cover_severities():
    generated = anomalies.many_anomalies(20)

    assert len(generated) == 20
    assert len({a.product_id for a in generated}) == 20
    assert {a.severity for a in generated} == set(AnomalySeverity)
