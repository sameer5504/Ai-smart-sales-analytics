"""Forecast output contract for the revenue forecasting feature.

This is the shape returned by the forecast endpoint and consumed by the
dashboard and the forecast chart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Status values.
STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"

# Model names (which model produced the forecast).
MODEL_MOVING_AVERAGE = "moving_average"
MODEL_LINEAR_TREND = "linear_trend"
MODEL_SEASONAL_HOLIDAY = "seasonal_holiday"
MODEL_TRAINED = "trained_revenue"
MODEL_AUTOML = "automl_endpoint"

# Machine-readable reasons for an unavailable forecast.
REASON_INSUFFICIENT_HISTORY = "insufficient_history"
REASON_MODEL_UNAVAILABLE = "model_unavailable"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MonthlyPoint:
    """One point of the monthly revenue series (used to draw history)."""

    month: str  # "YYYY-MM"
    revenue: float

    def to_dict(self) -> dict:
        return {"month": self.month, "revenue": self.revenue}


@dataclass
class PredictionInterval:
    """Optional uncertainty range around the forecast (models that provide it)."""

    lower: float
    upper: float

    def to_dict(self) -> dict:
        return {"lower": self.lower, "upper": self.upper}


@dataclass
class ForecastResult:
    """The forecast result returned to the frontend.

    Use the ``available`` / ``unavailable`` constructors rather than building
    this directly, so required fields for each case are always set.
    """

    status: str  # STATUS_AVAILABLE | STATUS_UNAVAILABLE
    target_month: str  # month being forecast, "YYYY-MM"
    history: list[MonthlyPoint] = field(default_factory=list)
    predicted_revenue: float | None = None
    currency: str | None = None
    model: str | None = None  # which rung produced it; None when unavailable
    interval: PredictionInterval | None = None
    reason: str | None = None  # machine code, set when unavailable
    message: str | None = None  # human-readable explanation
    generated_at: str = field(default_factory=_utc_now_iso)

    @classmethod
    def available(
        cls,
        *,
        target_month: str,
        predicted_revenue: float,
        model: str,
        history: list[MonthlyPoint],
        currency: str | None = None,
        interval: PredictionInterval | None = None,
    ) -> ForecastResult:
        """Build a successful forecast result."""
        return cls(
            status=STATUS_AVAILABLE,
            target_month=target_month,
            predicted_revenue=predicted_revenue,
            model=model,
            history=list(history),
            currency=currency,
            interval=interval,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        target_month: str,
        reason: str,
        message: str,
        history: list[MonthlyPoint] | None = None,
    ) -> ForecastResult:
        """Build an unavailable result (e.g. not enough history)."""
        return cls(
            status=STATUS_UNAVAILABLE,
            target_month=target_month,
            reason=reason,
            message=message,
            history=list(history or []),
        )

    def to_dict(self) -> dict:
        """Serialize to the JSON shape the API returns."""
        return {
            "status": self.status,
            "target_month": self.target_month,
            "predicted_revenue": self.predicted_revenue,
            "currency": self.currency,
            "model": self.model,
            "history": [point.to_dict() for point in self.history],
            "interval": self.interval.to_dict() if self.interval else None,
            "reason": self.reason,
            "message": self.message,
            "generated_at": self.generated_at,
        }
