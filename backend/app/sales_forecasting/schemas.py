from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Base configuration shared by sales-forecast output models."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )


class ForecastFrequency(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ForecastStatus(StrEnum):
    FORECASTABLE = "forecastable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    NO_SALES_HISTORY = "no_sales_history"


class ForecastModel(StrEnum):
    MOVING_AVERAGE_3 = "moving_average_3"


class ProductSalesForecast(ContractModel):
    """Forecast result for one product and one future period."""

    product_id: str = Field(min_length=1)

    frequency: ForecastFrequency

    forecast_period_start: date
    forecast_period_end: date

    forecast_quantity: float | None = Field(
        default=None,
        ge=0,
    )

    forecast_status: ForecastStatus

    model: ForecastModel | None = None

    history_periods: int = Field(
        ge=0,
    )

    nonzero_periods: int = Field(
        ge=0,
    )

    @model_validator(mode="after")
    def validate_forecast_semantics(
        self,
    ) -> Self:
        if self.forecast_period_end < self.forecast_period_start:
            raise ValueError(
                "forecast_period_end must not be before "
                "forecast_period_start."
            )

        if self.nonzero_periods > self.history_periods:
            raise ValueError(
                "nonzero_periods cannot exceed history_periods."
            )

        if self.forecast_status == ForecastStatus.FORECASTABLE:
            if self.forecast_quantity is None:
                raise ValueError(
                    "A forecastable result must contain "
                    "forecast_quantity."
                )

            if self.model is None:
                raise ValueError(
                    "A forecastable result must contain a model."
                )

        else:
            if self.forecast_quantity is not None:
                raise ValueError(
                    "An unavailable forecast must have "
                    "forecast_quantity=null."
                )

            if self.model is not None:
                raise ValueError(
                    "An unavailable forecast must have model=null."
                )

        return self


class SalesForecastResponse(ContractModel):
    """Public response returned by the sales-forecasting feature."""

    schema_version: Literal["1.0"] = "1.0"
    data_type: Literal["sales"] = "sales"

    forecasts: list[ProductSalesForecast]
