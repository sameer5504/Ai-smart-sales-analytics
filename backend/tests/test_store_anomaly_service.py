from datetime import date, timedelta

import pandas as pd

from app.anomaly.schemas import (
    AnomalyMetric,
    AnomalyScope,
    AnomalySeverity,
    AnomalyType,
)
from app.services.store_anomaly_service import (
    calculate_store_historical_baselines,
    detect_store_anomalies,
)


def _weekly_rows(
    quantities: list[float],
    prices: list[float],
) -> pd.DataFrame:
    start = date(2026, 1, 5)

    rows = [
        {
            "transaction_date": (start + timedelta(weeks=index)),
            "quantity": quantity,
            "unit_price": price,
        }
        for index, (quantity, price) in enumerate(zip(quantities, prices, strict=True))
    ]

    return pd.DataFrame(rows)


def _dated_rows(
    dates: list[date],
    quantities: list[float],
    prices: list[float],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_date": transaction_date,
                "quantity": quantity,
                "unit_price": price,
            }
            for transaction_date, quantity, price in zip(
                dates,
                quantities,
                prices,
                strict=True,
            )
        ]
    )


def test_store_units_drop_is_detected_independently_from_revenue():
    df = _weekly_rows(
        [100, 100, 100, 100, 50],
        [10, 10, 10, 10, 30],
    )

    anomalies = detect_store_anomalies(df)

    assert len(anomalies) == 1

    anomaly = anomalies[0]

    assert anomaly.scope == AnomalyScope.STORE
    assert anomaly.metric == AnomalyMetric.UNITS_SOLD
    assert anomaly.anomaly_type == AnomalyType.SHARP_DROP
    assert anomaly.baseline_value == 100
    assert anomaly.current_value == 50
    assert anomaly.change_percent == -50
    assert anomaly.product_id is None


def test_store_revenue_spike_is_detected_independently_from_units():
    df = _weekly_rows(
        [10, 10, 10, 10, 10],
        [10, 10, 10, 10, 25],
    )

    anomalies = detect_store_anomalies(df)

    assert len(anomalies) == 1

    anomaly = anomalies[0]

    assert anomaly.scope == AnomalyScope.STORE
    assert anomaly.metric == AnomalyMetric.REVENUE
    assert anomaly.anomaly_type == AnomalyType.UNUSUAL_INCREASE
    assert anomaly.baseline_value == 100
    assert anomaly.current_value == 250
    assert anomaly.change_percent == 150


def test_store_drop_at_threshold_is_detected_for_both_metrics():
    df = _weekly_rows(
        [100, 100, 100, 100, 50],
        [10, 10, 10, 10, 10],
    )

    anomalies = detect_store_anomalies(df)

    assert len(anomalies) == 2

    assert {anomaly.metric for anomaly in anomalies} == {
        AnomalyMetric.UNITS_SOLD,
        AnomalyMetric.REVENUE,
    }

    assert all(anomaly.anomaly_type == AnomalyType.SHARP_DROP for anomaly in anomalies)


def test_store_change_inside_threshold_is_not_flagged():
    df = _weekly_rows(
        [100, 100, 100, 100, 60],
        [10, 10, 10, 10, 10],
    )

    assert detect_store_anomalies(df) == []


def test_store_detection_requires_four_historical_periods():
    df = _weekly_rows(
        [100, 100, 10],
        [10, 10, 10],
    )

    assert detect_store_anomalies(df) == []


def test_historical_baseline_uses_previous_four_periods_only():
    df = _weekly_rows(
        [10, 30, 20, 40, 999],
        [1, 1, 1, 1, 1],
    )

    baselines = calculate_store_historical_baselines(df)

    assert baselines[AnomalyMetric.UNITS_SOLD] == 25
    assert baselines[AnomalyMetric.REVENUE] == 25


def test_business_histories_produce_independent_baselines():
    first_business = _weekly_rows(
        [100, 100, 100, 100, 50],
        [10, 10, 10, 10, 10],
    )

    second_business = _weekly_rows(
        [20, 20, 20, 20, 10],
        [5, 5, 5, 5, 5],
    )

    first_baselines = calculate_store_historical_baselines(first_business)
    second_baselines = calculate_store_historical_baselines(second_business)

    assert first_baselines[AnomalyMetric.UNITS_SOLD] == 100
    assert second_baselines[AnomalyMetric.UNITS_SOLD] == 20

    assert first_baselines[AnomalyMetric.REVENUE] == 1000
    assert second_baselines[AnomalyMetric.REVENUE] == 100


def test_historical_baseline_requires_enough_history():
    df = _weekly_rows(
        [100, 100, 50],
        [10, 10, 10],
    )

    assert calculate_store_historical_baselines(df) == {}


def test_repeated_seasonal_drop_is_not_flagged():
    df = _dated_rows(
        [
            date(2024, 1, 8),
            date(2025, 1, 6),
            date(2025, 12, 8),
            date(2025, 12, 15),
            date(2025, 12, 22),
            date(2025, 12, 29),
            date(2026, 1, 5),
        ],
        [20, 22, 100, 100, 100, 100, 21],
        [10, 10, 10, 10, 10, 10, 10],
    )

    assert detect_store_anomalies(df) == []


def test_true_anomaly_is_not_hidden_by_seasonal_filter():
    df = _dated_rows(
        [
            date(2024, 1, 8),
            date(2025, 1, 6),
            date(2025, 12, 8),
            date(2025, 12, 15),
            date(2025, 12, 22),
            date(2025, 12, 29),
            date(2026, 1, 5),
        ],
        [20, 22, 100, 100, 100, 100, 5],
        [10, 10, 10, 10, 10, 10, 10],
    )

    anomalies = detect_store_anomalies(df)

    assert len(anomalies) == 2

    assert {anomaly.metric for anomaly in anomalies} == {
        AnomalyMetric.UNITS_SOLD,
        AnomalyMetric.REVENUE,
    }

    assert all(anomaly.anomaly_type == AnomalyType.SHARP_DROP for anomaly in anomalies)


def test_one_previous_season_is_not_enough_to_filter():
    df = _dated_rows(
        [
            date(2025, 1, 6),
            date(2025, 12, 8),
            date(2025, 12, 15),
            date(2025, 12, 22),
            date(2025, 12, 29),
            date(2026, 1, 5),
        ],
        [20, 100, 100, 100, 100, 20],
        [10, 10, 10, 10, 10, 10],
    )

    anomalies = detect_store_anomalies(df)

    assert len(anomalies) == 2


def test_store_severity_uses_centralized_rules():
    critical_drop_df = _weekly_rows(
        [100, 100, 100, 100, 20],
        [10, 10, 10, 10, 10],
    )

    anomalies = detect_store_anomalies(critical_drop_df)

    assert len(anomalies) == 2

    assert all(anomaly.severity == AnomalySeverity.CRITICAL for anomaly in anomalies)


def test_store_unusual_increase_can_be_info():
    increase_df = _weekly_rows(
        [100, 100, 100, 100, 200],
        [10, 10, 10, 10, 10],
    )

    anomalies = detect_store_anomalies(increase_df)

    assert len(anomalies) == 2

    assert all(anomaly.severity == AnomalySeverity.INFO for anomaly in anomalies)
