"""Revenue forecasting feature (US-3.2.1)."""

from app.forecast.contract import (
    ForecastResult,
    MonthlyPoint,
    PredictionInterval,
)
from app.forecast.daily_series import (
    DailyRevenueSeries,
    build_daily_revenue_series,
)
from app.forecast.holiday_calendar import (
    holiday_calendar,
    supported_regions,
)
from app.forecast.simple_models import (
    linear_trend_forecast,
    moving_average_forecast,
)

__all__ = [
    "DailyRevenueSeries",
    "ForecastResult",
    "MonthlyPoint",
    "PredictionInterval",
    "build_daily_revenue_series",
    "holiday_calendar",
    "linear_trend_forecast",
    "moving_average_forecast",
    "supported_regions",
]
