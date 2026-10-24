from __future__ import annotations

import pandas as pd

from app.sales_forecasting.history import (
    build_product_sales_history,
)
from app.sales_forecasting.model import (
    forecast_from_history,
)
from app.sales_forecasting.schemas import (
    ForecastFrequency,
    ForecastModel,
    ForecastStatus,
    ProductSalesForecast,
    SalesForecastResponse,
)


def _period_frequency(
    frequency: ForecastFrequency,
) -> str:
    """Map the public frequency to pandas period notation."""
    if frequency == ForecastFrequency.WEEKLY:
        return "W-SUN"

    if frequency == ForecastFrequency.MONTHLY:
        return "M"

    raise ValueError(
        f"Unsupported forecast frequency: {frequency}"
    )


def _next_forecast_period(
    data: pd.DataFrame,
    frequency: ForecastFrequency,
) -> pd.Period | None:
    """
    Return the first full future period after the latest transaction.

    Example:
      latest transaction = 2026-04-15
      monthly forecast   = 2026-05

    The partial April period is not used as a training period.
    """
    if (
        data.empty
        or "transaction_date" not in data.columns
    ):
        return None

    dates = pd.to_datetime(
        data["transaction_date"],
        errors="coerce",
    ).dropna()

    if dates.empty:
        return None

    period_frequency = _period_frequency(
        frequency
    )

    latest_period = (
        dates.max()
        .to_period(period_frequency)
    )

    return latest_period + 1


def forecast_product_sales(
    data: pd.DataFrame,
    frequency: ForecastFrequency,
) -> SalesForecastResponse:
    """
    Generate one-period-ahead sales forecasts for products.

    Input:
        Cleaned, standardised sales rows from the data pipeline.

    Process:
        1. Build continuous product sales history.
        2. Aggregate signed quantity by period.
        3. Determine history sufficiency.
        4. Forecast with Moving Average (3) when sufficient.
        5. Return the public output contract.
    """
    frequency = ForecastFrequency(
        frequency
    )

    history = build_product_sales_history(
        data,
        frequency,
    )

    if history.empty:
        return SalesForecastResponse(
            forecasts=[]
        )

    forecast_period = (
        _next_forecast_period(
            data,
            frequency,
        )
    )

    if forecast_period is None:
        return SalesForecastResponse(
            forecasts=[]
        )

    forecasts: list[
        ProductSalesForecast
    ] = []

    for (
        product_id,
        product_history,
    ) in history.groupby(
        "product_id",
        sort=False,
    ):
        product_history = (
            product_history
            .sort_values("period")
            .reset_index(drop=True)
        )

        values = (
            product_history[
                "forecast_quantity"
            ]
            .astype(float)
            .to_numpy()
        )

        nonzero_periods = int(
            (values > 0).sum()
        )

        (
            status,
            prediction,
        ) = forecast_from_history(
            values
        )

        model = (
            ForecastModel.MOVING_AVERAGE_3
            if status
            == ForecastStatus.FORECASTABLE
            else None
        )

        forecasts.append(
            ProductSalesForecast(
                product_id=str(
                    product_id
                ),
                frequency=frequency,
                forecast_period_start=(
                    forecast_period
                    .start_time
                    .date()
                ),
                forecast_period_end=(
                    forecast_period
                    .end_time
                    .date()
                ),
                forecast_quantity=(
                    prediction
                ),
                forecast_status=status,
                model=model,
                history_periods=len(
                    product_history
                ),
                nonzero_periods=(
                    nonzero_periods
                ),
            )
        )

    return SalesForecastResponse(
        forecasts=forecasts
    )
