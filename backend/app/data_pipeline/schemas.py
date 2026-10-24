from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DataType(StrEnum):
    SALES = "sales"
    CUSTOMERS = "customers"
    FEEDBACK = "feedback"


class FieldSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["date", "string", "number"]
    description: str


class ExpectedDataTypeSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_type: DataType
    row_granularity: str
    required_fields: dict[str, FieldSchema]
    optional_fields: dict[str, FieldSchema]


SALES_EXPECTED_SCHEMA = ExpectedDataTypeSchema(
    data_type=DataType.SALES,
    row_granularity="one_product_per_order",
    required_fields={
        "transaction_date": FieldSchema(
            type="date",
            description="The date on which the transaction occurred.",
        ),
        "order_id": FieldSchema(
            type="string",
            description="A unique identifier for the order or transaction.",
        ),
        "product_id": FieldSchema(
            type="string",
            description="A unique identifier for the product.",
        ),
        "product_name": FieldSchema(
            type="string",
            description="The displayed name of the product.",
        ),
        "quantity": FieldSchema(
            type="number",
            description="The number of units sold.",
        ),
        "unit_price": FieldSchema(
            type="number",
            description="The selling price of one unit.",
        ),
    },
    optional_fields={
        "category": FieldSchema(
            type="string",
            description="The category to which the product belongs.",
        ),
    },
)


EXPECTED_SCHEMAS: dict[str, ExpectedDataTypeSchema] = {
    DataType.SALES.value: SALES_EXPECTED_SCHEMA,
}
