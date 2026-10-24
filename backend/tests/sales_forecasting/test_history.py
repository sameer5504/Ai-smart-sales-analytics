import pandas as pd
import pytest

from app.sales_forecasting.history import (
    build_product_sales_history,
)
from app.sales_forecasting.schemas import (
    ForecastFrequency,
)


def test_missing_required_fields_raise_error():
    data = pd.DataFrame(
        {
            "product_id": ["A"],
            "quantity": [10],
        }
    )

    with pytest.raises(
        ValueError,
        match="transaction_date",
    ):
        build_product_sales_history(
            data,
            ForecastFrequency.MONTHLY,
        )


def test_signed_quantities_are_aggregated_and_negative_target_is_clipped():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-01-10",
                "2026-03-31",
            ],
            "product_id": [
                "A",
                "A",
                "A",
            ],
            "quantity": [
                10,
                -15,
                20,
            ],
        }
    )

    history = build_product_sales_history(
        data,
        ForecastFrequency.MONTHLY,
    )

    january = history.loc[
        history["period"].astype(str)
        == "2026-01"
    ].iloc[0]

    assert january["net_quantity"] == -5
    assert january["forecast_quantity"] == 0


def test_missing_month_is_zero_filled():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-03-31",
            ],
            "product_id": [
                "A",
                "A",
            ],
            "quantity": [
                10,
                20,
            ],
        }
    )

    history = build_product_sales_history(
        data,
        ForecastFrequency.MONTHLY,
    )

    february = history.loc[
        history["period"].astype(str)
        == "2026-02"
    ].iloc[0]

    assert february["net_quantity"] == 0
    assert february["forecast_quantity"] == 0
    assert february["transaction_rows"] == 0
    assert bool(
        february["was_observed"]
    ) is False


def test_product_history_does_not_start_before_first_product_period():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-10",
                "2026-03-31",
            ],
            "product_id": [
                "A",
                "B",
                "A",
            ],
            "quantity": [
                10,
                5,
                20,
            ],
        }
    )

    history = build_product_sales_history(
        data,
        ForecastFrequency.MONTHLY,
    )

    product_b = history.loc[
        history["product_id"] == "B"
    ]

    assert (
        product_b["period"]
        .astype(str)
        .iloc[0]
        == "2026-02"
    )


def test_numeric_product_id_does_not_gain_decimal_suffix():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-01-31",
            ],
            "product_id": [
                12345.0,
                12345.0,
            ],
            "quantity": [
                10,
                5,
            ],
        }
    )

    history = build_product_sales_history(
        data,
        ForecastFrequency.MONTHLY,
    )

    assert (
        history["product_id"].unique().tolist()
        == ["12345"]
    )


def test_partial_boundary_weeks_are_excluded():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-07",  # partial first week
                "2026-01-14",  # complete week
                "2026-01-20",  # complete week
                "2026-01-25",  # closes final week
            ],
            "product_id": [
                "A",
                "A",
                "A",
                "A",
            ],
            "quantity": [
                100,
                10,
                20,
                5,
            ],
        }
    )

    history = build_product_sales_history(
        data,
        ForecastFrequency.WEEKLY,
    )

    periods = (
        history["period"]
        .astype(str)
        .tolist()
    )

    assert periods == [
        "2026-01-12/2026-01-18",
        "2026-01-19/2026-01-25",
    ]

    assert (
        history["forecast_quantity"]
        .tolist()
        == [10.0, 25.0]
    )


def test_empty_dataframe_returns_empty_history():
    data = pd.DataFrame(
        columns=[
            "transaction_date",
            "product_id",
            "quantity",
        ]
    )

    history = build_product_sales_history(
        data,
        ForecastFrequency.MONTHLY,
    )

    assert history.empty

    assert list(history.columns) == [
        "product_id",
        "period",
        "period_start",
        "period_end",
        "net_quantity",
        "forecast_quantity",
        "transaction_rows",
        "was_observed",
    ]
