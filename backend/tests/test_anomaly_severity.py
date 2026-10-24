import pytest

from app.anomaly.schemas import (
    AnomalySeverity,
    AnomalyType,
)
from app.services.anomaly_severity import (
    classify_anomaly_severity,
)


@pytest.mark.parametrize(
    ("change_percent", "expected"),
    [
        (-50.0, AnomalySeverity.WARNING),
        (-74.99, AnomalySeverity.WARNING),
        (-75.0, AnomalySeverity.CRITICAL),
        (-90.0, AnomalySeverity.CRITICAL),
    ],
)
def test_sharp_drop_severity(
    change_percent,
    expected,
):
    assert (
        classify_anomaly_severity(
            AnomalyType.SHARP_DROP,
            change_percent,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("change_percent", "expected"),
    [
        (100.0, AnomalySeverity.INFO),
        (199.99, AnomalySeverity.INFO),
        (200.0, AnomalySeverity.WARNING),
        (300.0, AnomalySeverity.WARNING),
    ],
)
def test_unusual_increase_severity(
    change_percent,
    expected,
):
    assert (
        classify_anomaly_severity(
            AnomalyType.UNUSUAL_INCREASE,
            change_percent,
        )
        == expected
    )


def test_dead_stock_is_always_critical():
    assert (
        classify_anomaly_severity(
            AnomalyType.DEAD_STOCK,
            -100.0,
        )
        == AnomalySeverity.CRITICAL
    )


def test_missing_change_defaults_to_warning():
    assert (
        classify_anomaly_severity(
            AnomalyType.SHARP_DROP,
            None,
        )
        == AnomalySeverity.WARNING
    )
