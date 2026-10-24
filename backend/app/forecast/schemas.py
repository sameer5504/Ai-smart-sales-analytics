"""Request schema for the forecast endpoint."""

from pydantic import BaseModel, Field


class SaleRecord(BaseModel):
    """One standardized sales line item."""

    transaction_date: str
    quantity: float
    unit_price: float


class ForecastRequest(BaseModel):
    """Sales history to forecast from, plus optional region for holidays."""

    records: list[SaleRecord] = Field(
        default_factory=list,
        description="Standardized sales line items (transaction_date, quantity, unit_price).",
    )
    region: str | None = Field(
        default=None,
        description="Account region for the holiday calendar, e.g. 'middle_east'.",
    )
    country: str | None = Field(
        default=None,
        description="Holiday calendar country code (e.g. 'GB', 'PS'); overrides region when set.",
    )
