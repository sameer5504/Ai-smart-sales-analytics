from datetime import date

import pytest
from pydantic import ValidationError

from app.sales_forecasting.schemas import (
    ForecastFrequency,
    ForecastModel,
    ForecastStatus,
    ProductSalesForecast,
)


def make_forecast(**overrides):
    values = {
        "product_id": "A",
        "frequency": ForecastFrequency.MONTHLY,
        "forecast_period_start": date(2026, 5, 1),
        "forecast_period_end": date(2026, 5, 31),
        "forecast_quantity": 12.5,
        "forecast_status": ForecastStatus.FORECASTABLE,
        "model": ForecastModel.MOVING_AVERAGE_3,
        "history_periods": 12,
        "nonzero_periods": 8,
    }

    values.update(overrides)

    return ProductSalesForecast(
        **values
    )


def test_forecastable_result_is_valid():
    result = make_forecast()

    assert result.forecast_quantity == 12.5
    assert (
        result.forecast_status
        == ForecastStatus.FORECASTABLE
    )
    assert (
        result.model
        == ForecastModel.MOVING_AVERAGE_3
    )


def test_forecastable_result_requires_quantity():
    with pytest.raises(
        ValidationError,
        match="must contain forecast_quantity",
    ):
        make_forecast(
            forecast_quantity=None,
        )


def test_forecastable_result_requires_model():
    with pytest.raises(
        ValidationError,
        match="must contain a model",
    ):
        make_forecast(
            model=None,
        )


@pytest.mark.parametrize(
    "status",
    [
        ForecastStatus.INSUFFICIENT_HISTORY,
        ForecastStatus.NO_SALES_HISTORY,
    ],
)
def test_unavailable_result_requires_null_quantity_and_model(
    status,
):
    result = make_forecast(
        forecast_status=status,
        forecast_quantity=None,
        model=None,
    )

    assert result.forecast_quantity is None
    assert result.model is None


def test_unavailable_result_rejects_quantity():
    with pytest.raises(
        ValidationError,
        match="forecast_quantity=null",
    ):
        make_forecast(
            forecast_status=(
                ForecastStatus.INSUFFICIENT_HISTORY
            ),
            forecast_quantity=5.0,
            model=None,
        )


def test_unavailable_result_rejects_model():
    with pytest.raises(
        ValidationError,
        match="model=null",
    ):
        make_forecast(
            forecast_status=(
                ForecastStatus.INSUFFICIENT_HISTORY
            ),
            forecast_quantity=None,
            model=ForecastModel.MOVING_AVERAGE_3,
        )


def test_negative_forecast_quantity_is_rejected():
    with pytest.raises(
        ValidationError,
    ):
        make_forecast(
            forecast_quantity=-1,
        )


def test_nonzero_periods_cannot_exceed_history_periods():
    with pytest.raises(
        ValidationError,
        match="cannot exceed history_periods",
    ):
        make_forecast(
            history_periods=2,
            nonzero_periods=3,
        )


def test_forecast_period_end_cannot_precede_start():
    with pytest.raises(
        ValidationError,
        match="must not be before",
    ):
        make_forecast(
            forecast_period_start=date(
                2026,
                5,
                31,
            ),
            forecast_period_end=date(
                2026,
                5,
                1,
            ),
        )
