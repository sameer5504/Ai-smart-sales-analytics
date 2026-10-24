import pandas as pd

from app.recommendations.evidence import (
    build_evidence,
    calculate_units_lost,
)
from tests.fixtures import anomalies


def test_calculate_units_lost_returns_none_without_baseline():
    anomaly = anomalies.DEAD_STOCK

    assert calculate_units_lost(anomaly) is None


def test_calculate_units_lost_for_shortfall():
    anomaly = anomalies.SHARP_DROP

    assert calculate_units_lost(anomaly) is not None


def test_build_evidence_carries_anomaly_values(monkeypatch):
    df = pd.DataFrame(
        {
            "revenue": [100.0],
            "product_id": [anomalies.SHARP_DROP.product_id],
            "unit_price": [10.0],
        }
    )

    monkeypatch.setattr(
        "app.recommendations.evidence.load_cleaned",
        lambda user_id, filename: df,
    )

    evidence = build_evidence(
        anomalies.SHARP_DROP,
        1,
        "test.csv",
    )

    assert evidence.metric == anomalies.SHARP_DROP.metric
    assert evidence.current_value == anomalies.SHARP_DROP.current_value
    assert evidence.period_start == anomalies.SHARP_DROP.period_start
    assert evidence.period_end == anomalies.SHARP_DROP.period_end
