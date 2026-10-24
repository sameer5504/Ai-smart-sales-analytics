from pydantic import BaseModel


class KpiValue(BaseModel):
    label: str
    value: str | None = None
    delta_pct: float | None = None
    period_label: str
    available: bool = True
    unavailable_reason: str | None = None


class MonthlyPoint(BaseModel):
    month: str
    value: float


class TopProduct(BaseModel):
    name: str
    value: float


class DashboardResponse(BaseModel):
    kpis: list[KpiValue]
    revenue_over_time: list[MonthlyPoint]
    units_over_time: list[MonthlyPoint]
    top_products: list[TopProduct]


# --- Raw-data contract for /api/dashboard/detailed ---


class DashboardRow(BaseModel):
    date: str
    order_id: str
    product_id: str
    product_name: str
    category: str | None = None
    quantity: float
    unit_price: float
    revenue: float


class DataQuality(BaseModel):
    total_rows: int


class DashboardDetailedResponse(BaseModel):
    data: list[DashboardRow]
    data_quality: DataQuality
