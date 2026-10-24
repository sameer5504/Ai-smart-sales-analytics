from datetime import date

import pandas as pd
import pytest

from app.sales_forecasting.schemas import (
    ForecastFrequency,
    ForecastModel,
    ForecastStatus,
)
from app.sales_forecasting.service import (
    forecast_product_sales,
)


def test_monthly_forecast_uses_last_three_complete_months():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-15",
            ],
            "product_id": [
                "A",
                "A",
                "A",
                "A",
            ],
            "quantity": [
                10,
                20,
                30,
                999,
            ],
        }
    )

    result = forecast_product_sales(
        data,
        ForecastFrequency.MONTHLY,
    )

    assert len(result.forecasts) == 1

    forecast = result.forecasts[0]

    assert (
        forecast.product_id
        == "A"
    )

    assert (
        forecast.forecast_status
        == ForecastStatus.FORECASTABLE
    )

    assert (
        forecast.model
        == ForecastModel.MOVING_AVERAGE_3
    )

    assert (
        forecast.forecast_quantity
        == pytest.approx(20.0)
    )

    # April is partial, so the next FULL future
    # monthly period is May.
    assert (
        forecast.forecast_period_start
        == date(2026, 5, 1)
    )

    assert (
        forecast.forecast_period_end
        == date(2026, 5, 31)
    )


def test_partial_month_is_not_used_in_model():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-15",
            ],
            "product_id": [
                "A",
                "A",
                "A",
                "A",
            ],
            "quantity": [
                3,
                6,
                9,
                10000,
            ],
        }
    )

    forecast = forecast_product_sales(
        data,
        ForecastFrequency.MONTHLY,
    ).forecasts[0]

    assert (
        forecast.forecast_quantity
        == pytest.approx(6.0)
    )


def test_insufficient_history_returns_null_forecast():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-04-15",
            ],
            "product_id": [
                "A",
                "A",
                "A",
            ],
            "quantity": [
                10,
                20,
                50,
            ],
        }
    )

    forecast = forecast_product_sales(
        data,
        ForecastFrequency.MONTHLY,
    ).forecasts[0]

    assert (
        forecast.forecast_status
        == ForecastStatus.INSUFFICIENT_HISTORY
    )

    assert (
        forecast.forecast_quantity
        is None
    )

    assert forecast.model is None


def test_no_positive_sales_history_is_unavailable():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-15",
            ],
            "product_id": [
                "A",
                "A",
                "A",
                "A",
            ],
            "quantity": [
                -5,
                -2,
                -1,
                -4,
            ],
        }
    )

    forecast = forecast_product_sales(
        data,
        ForecastFrequency.MONTHLY,
    ).forecasts[0]

    assert (
        forecast.forecast_status
        == ForecastStatus.NO_SALES_HISTORY
    )

    assert (
        forecast.forecast_quantity
        is None
    )

    assert forecast.model is None


def test_weekly_forecast_period_is_next_full_week():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-05",
                "2026-01-12",
                "2026-01-19",
                "2026-01-28",
            ],
            "product_id": [
                "A",
                "A",
                "A",
                "A",
            ],
            "quantity": [
                3,
                6,
                9,
                500,
            ],
        }
    )

    forecast = forecast_product_sales(
        data,
        ForecastFrequency.WEEKLY,
    ).forecasts[0]

    assert (
        forecast.forecast_quantity
        == pytest.approx(6.0)
    )

    assert (
        forecast.forecast_period_start
        == date(2026, 2, 2)
    )

    assert (
        forecast.forecast_period_end
        == date(2026, 2, 8)
    )


def test_service_returns_one_result_per_product():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-15",
            ],
            "product_id": [
                "A",
                "A",
                "A",
                "B",
                "B",
                "B",
                "A",
            ],
            "quantity": [
                10,
                20,
                30,
                5,
                10,
                15,
                1,
            ],
        }
    )

    result = forecast_product_sales(
        data,
        ForecastFrequency.MONTHLY,
    )

    assert len(
        result.forecasts
    ) == 2

    assert {
        forecast.product_id
        for forecast in result.forecasts
    } == {
        "A",
        "B",
    }


def test_dataset_with_no_complete_period_returns_empty_response():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-04-15",
            ],
            "product_id": [
                "A",
            ],
            "quantity": [
                10,
            ],
        }
    )

    result = forecast_product_sales(
        data,
        ForecastFrequency.MONTHLY,
    )

    assert result.forecasts == []
