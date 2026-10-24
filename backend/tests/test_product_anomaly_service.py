from datetime import date, timedelta

import pandas as pd
import pytest

from app.anomaly.schemas import (
    AnomalySeverity,
    AnomalyType,
)
from app.services.product_anomaly_service import (
    ProductAnomalyConfig,
    detect_dead_stock,
    detect_product_anomalies,
    detect_sharp_drops,
    detect_unusual_increases,
)


@pytest.fixture
def sales_rows():
    """Factory fixture for building product sales rows."""

    def _make_sales_rows(
        product_id: str,
        weekly_units: list[float],
        name: str | None = None,
    ):
        rows = []
        start = date(2026, 1, 5)
        product_name = name or f"Product {product_id}"

        for index, quantity in enumerate(weekly_units):
            if quantity <= 0:
                continue

            rows.append(
                {
                    "transaction_date": start + timedelta(weeks=index),
                    "order_id": f"{product_id}-{index}",
                    "product_id": product_id,
                    "product_name": product_name,
                    "quantity": quantity,
                    "unit_price": 10.0,
                }
            )

        return rows

    return _make_sales_rows


@pytest.fixture
def store_anchor(sales_rows):
    """
    Factory fixture that keeps every weekly period active at store level
    so product-level zeros are distinguishable from a whole-store
    closed/non-trading week.
    """

    def _make_store_anchor(weeks: int):
        return sales_rows(
            "ANCHOR",
            [1] * weeks,
            "Store Anchor",
        )

    return _make_store_anchor


@pytest.fixture
def sales_dataframe():
    """Factory fixture for combining row groups into a DataFrame."""

    def _make_dataframe(*groups):
        rows = []

        for group in groups:
            rows.extend(group)

        return pd.DataFrame(rows)

    return _make_dataframe


def test_sharp_drop_is_flagged_at_threshold(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(5),
        sales_rows(
            "DROP",
            [100, 100, 100, 100, 50],
        ),
    )

    anomalies = detect_sharp_drops(df)

    assert len(anomalies) == 1

    anomaly = anomalies[0]

    assert anomaly.product_id == "DROP"
    assert anomaly.anomaly_type == AnomalyType.SHARP_DROP
    assert anomaly.baseline_value == 100
    assert anomaly.current_value == 50
    assert anomaly.change_percent == -50
    assert anomalies[0].severity == AnomalySeverity.WARNING


def test_drop_just_inside_normal_range_is_not_flagged(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(5),
        sales_rows(
            "NORMAL",
            [100, 100, 100, 100, 51],
        ),
    )

    assert detect_sharp_drops(df) == []


def test_established_product_with_four_zero_active_weeks_is_dead_stock(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(8),
        sales_rows(
            "DEAD",
            [10, 12, 11, 9, 0, 0, 0, 0],
        ),
    )

    anomalies = detect_dead_stock(df)

    assert len(anomalies) == 1

    anomaly = anomalies[0]

    assert anomaly.product_id == "DEAD"
    assert anomaly.anomaly_type == AnomalyType.DEAD_STOCK
    assert anomaly.current_value == 0
    assert anomaly.change_percent == -100
    assert anomaly.period_start == date(2026, 2, 2)
    assert anomaly.period_end == date(2026, 3, 1)
    assert anomalies[0].severity == AnomalySeverity.CRITICAL


def test_new_product_is_not_misclassified_as_dead_stock(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(8),
        sales_rows(
            "NEW",
            [0, 0, 0, 10, 0, 0, 0, 0],
        ),
    )

    assert detect_dead_stock(df) == []


def test_unusual_increase_is_flagged_at_threshold(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(5),
        sales_rows(
            "SPIKE",
            [20, 20, 20, 20, 40],
        ),
    )

    anomalies = detect_unusual_increases(df)

    assert len(anomalies) == 1

    anomaly = anomalies[0]

    assert anomaly.product_id == "SPIKE"
    assert anomaly.anomaly_type == AnomalyType.UNUSUAL_INCREASE
    assert anomaly.baseline_value == 20
    assert anomaly.current_value == 40
    assert anomaly.change_percent == 100
    assert anomalies[0].severity == AnomalySeverity.INFO


def test_spike_just_below_threshold_is_not_flagged(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(5),
        sales_rows(
            "NORMAL",
            [20, 20, 20, 20, 39],
        ),
    )

    assert detect_unusual_increases(df) == []


def test_multi_product_dataset_returns_unified_anomalies(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    df = sales_dataframe(
        store_anchor(8),
        sales_rows(
            "DROP",
            [100, 100, 100, 100, 100, 100, 100, 40],
        ),
        sales_rows(
            "SPIKE",
            [20, 20, 20, 20, 20, 20, 20, 45],
        ),
        sales_rows(
            "DEAD",
            [10, 12, 11, 9, 0, 0, 0, 0],
        ),
        sales_rows(
            "NORMAL",
            [30, 30, 30, 30, 30, 30, 30, 28],
        ),
    )

    anomalies = detect_product_anomalies(df)

    by_product = {anomaly.product_id: anomaly for anomaly in anomalies}

    assert set(by_product) == {
        "DEAD",
        "DROP",
        "SPIKE",
    }

    assert by_product["DEAD"].anomaly_type == AnomalyType.DEAD_STOCK
    assert by_product["DROP"].anomaly_type == AnomalyType.SHARP_DROP
    assert by_product["SPIKE"].anomaly_type == AnomalyType.UNUSUAL_INCREASE

    assert all(anomaly.metric == "units_sold" for anomaly in anomalies)


def test_non_positive_sales_rows_are_excluded(
    sales_rows,
    store_anchor,
):
    config = ProductAnomalyConfig(min_baseline_units=1)

    rows = store_anchor(5) + sales_rows(
        "P1",
        [10, 10, 10, 10, 10],
    )

    rows.extend(
        [
            {
                "transaction_date": date(2026, 2, 2),
                "order_id": "RETURN",
                "product_id": "P1",
                "product_name": "Product P1",
                "quantity": -50,
                "unit_price": 10.0,
            },
            {
                "transaction_date": date(2026, 2, 2),
                "order_id": "FREE",
                "product_id": "P1",
                "product_name": "Product P1",
                "quantity": 500,
                "unit_price": 0.0,
            },
        ]
    )

    assert (
        detect_product_anomalies(
            pd.DataFrame(rows),
            config,
        )
        == []
    )


def test_order_id_starting_with_c_is_not_treated_as_cancelled(
    sales_rows,
    store_anchor,
):
    rows = store_anchor(5) + sales_rows(
        "P1",
        [10, 10, 10, 10, 10],
    )

    rows.append(
        {
            "transaction_date": date(2026, 2, 2),
            "order_id": "C12345",
            "product_id": "P1",
            "product_name": "Product P1",
            "quantity": 100,
            "unit_price": 10.0,
        }
    )

    anomalies = detect_unusual_increases(
        pd.DataFrame(rows),
        ProductAnomalyConfig(
            min_baseline_units=1,
        ),
    )

    assert len(anomalies) == 1
    assert anomalies[0].product_id == "P1"
    assert anomalies[0].anomaly_type == AnomalyType.UNUSUAL_INCREASE


def test_product_name_comes_from_most_recent_transaction(
    sales_rows,
    store_anchor,
    sales_dataframe,
):
    product_rows = sales_rows(
        "P1",
        [100, 100, 100, 100, 50],
        "Old Name",
    )

    product_rows[-1]["product_name"] = "New Name"

    product_rows = [
        product_rows[-1],
        *product_rows[:-1],
    ]

    df = sales_dataframe(
        store_anchor(5),
        product_rows,
    )

    anomalies = detect_sharp_drops(df)

    assert len(anomalies) == 1
    assert anomalies[0].product_id == "P1"
    assert anomalies[0].product_name == "New Name"
