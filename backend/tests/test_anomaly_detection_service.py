from datetime import date

import pandas as pd

from app.anomaly.schemas import (
    Anomaly,
    AnomalyMetric,
    AnomalyScope,
    AnomalySeverity,
    AnomalyType,
)
from app.services.anomaly_detection_service import (
    detect_anomalies,
)


def _store_anomaly() -> Anomaly:
    return Anomaly(
        anomaly_type=AnomalyType.SHARP_DROP,
        scope=AnomalyScope.STORE,
        metric=AnomalyMetric.REVENUE,
        severity=AnomalySeverity.CRITICAL,
        period_start=date(2026, 1, 5),
        period_end=date(2026, 1, 11),
        current_value=200.0,
        baseline_value=1000.0,
        change_percent=-80.0,
        message="Store revenue dropped sharply.",
    )


def _product_anomaly() -> Anomaly:
    return Anomaly(
        anomaly_type=AnomalyType.DEAD_STOCK,
        scope=AnomalyScope.PRODUCT,
        metric=AnomalyMetric.UNITS_SOLD,
        severity=AnomalySeverity.CRITICAL,
        product_id="P-100",
        product_name="Widget",
        period_start=date(2026, 1, 5),
        period_end=date(2026, 2, 1),
        current_value=0.0,
        baseline_value=10.0,
        change_percent=-100.0,
        message="Product P-100 stopped selling.",
    )


def test_detect_anomalies_combines_store_and_product_results(
    monkeypatch,
):
    store_anomaly = _store_anomaly()
    product_anomaly = _product_anomaly()

    monkeypatch.setattr(
        "app.services.anomaly_detection_service.detect_store_anomalies",
        lambda _df: [store_anomaly],
    )

    monkeypatch.setattr(
        "app.services.anomaly_detection_service.detect_product_anomalies",
        lambda _df: [product_anomaly],
    )

    result = detect_anomalies(pd.DataFrame())

    assert result == [
        store_anomaly,
        product_anomaly,
    ]

    assert all(isinstance(anomaly, Anomaly) for anomaly in result)


def test_detect_anomalies_returns_empty_list_when_none_found(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.anomaly_detection_service.detect_store_anomalies",
        lambda _df: [],
    )

    monkeypatch.setattr(
        "app.services.anomaly_detection_service.detect_product_anomalies",
        lambda _df: [],
    )

    assert detect_anomalies(pd.DataFrame()) == []
