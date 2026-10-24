import pandas as pd

from app.sales_forecasting.history import (
    build_product_sales_history,
)
from app.sales_forecasting.schemas import (
    ForecastFrequency,
)
from app.sales_forecasting.service import (
    forecast_product_sales,
)


def test_selected_frequency_changes_sales_aggregation():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-05",
                "2026-01-12",
                "2026-01-19",
                "2026-01-26",
                "2026-01-31",
                "2026-02-28",
            ],
            "product_id": ["A"] * 6,
            "quantity": [
                10,
                20,
                30,
                40,
                50,
                5,
            ],
        }
    )

    weekly = build_product_sales_history(
        data,
        ForecastFrequency.WEEKLY,
    )

    monthly = build_product_sales_history(
        data,
        ForecastFrequency.MONTHLY,
    )

    assert len(weekly) > len(monthly)

    assert (
        weekly["period"].iloc[0].freqstr
        == "W-SUN"
    )

    assert (
        monthly["period"].iloc[0].freqstr
        == "M"
    )


def test_weekly_selection_generates_weekly_forecast():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-05",
                "2026-01-12",
                "2026-01-19",
                "2026-01-28",
            ],
            "product_id": ["A"] * 4,
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
        ForecastFrequency.WEEKLY,
    )

    forecast = result.forecasts[0]

    assert (
        forecast.frequency
        == ForecastFrequency.WEEKLY
    )

    assert (
        forecast.forecast_period_start.weekday()
        == 0
    )

    assert (
        forecast.forecast_period_end.weekday()
        == 6
    )


def test_monthly_selection_generates_monthly_forecast():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-15",
            ],
            "product_id": ["A"] * 4,
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

    forecast = result.forecasts[0]

    assert (
        forecast.frequency
        == ForecastFrequency.MONTHLY
    )

    assert (
        forecast.forecast_period_start.day
        == 1
    )

    assert (
        forecast.forecast_period_end.month
        == forecast.forecast_period_start.month
    )


def test_string_frequency_can_be_selected_by_service():
    data = pd.DataFrame(
        {
            "transaction_date": [
                "2026-01-01",
                "2026-02-01",
                "2026-03-01",
                "2026-04-15",
            ],
            "product_id": ["A"] * 4,
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
        "monthly",
    )

    assert (
        result.forecasts[0].frequency
        == ForecastFrequency.MONTHLY
    )
