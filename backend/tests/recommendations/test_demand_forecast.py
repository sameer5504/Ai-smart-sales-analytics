"""Demand estimates when the product sales forecast is in play (US-4.3.5).

The forecast lands separately (US-3.1.1), so these run against a fake shaped
like its output. The live wiring is checked in test_demand_integration.py,
which starts running by itself once that module is on main.
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from app.recommendations.contract import DemandSource
from app.recommendations.demand import (
    REASON_INSUFFICIENT_HISTORY,
    REASON_NO_SALES_HISTORY,
    build_demand_estimates,
)

AHEAD_START = date(2026, 7, 1)
AHEAD_END = date(2026, 7, 31)


@dataclass
class FakeForecast:
    """One product's forecast, matching ProductSalesForecast's fields."""

    product_id: str
    forecast_quantity: float | None
    forecast_status: str
    forecast_period_start: date = AHEAD_START
    forecast_period_end: date = AHEAD_END


@dataclass
class FakeResponse:
    forecasts: list[FakeForecast] = field(default_factory=list)


def forecaster_returning(*forecasts):
    def forecaster(df, frequency):
        return FakeResponse(forecasts=list(forecasts))

    return forecaster


def failing_forecaster(df, frequency):
    raise RuntimeError("the forecaster fell over")


def frame(rows):
    return pd.DataFrame(
        rows,
        columns=["transaction_date", "product_id", "quantity"],
    )


# Two products, three finished months each, so trailing sales can always
# produce something to fall back to.
ROWS = frame(
    [
        ("2026-04-10", "P1", 10),
        ("2026-05-10", "P1", 20),
        ("2026-06-10", "P1", 30),
        ("2026-04-10", "P2", 5),
        ("2026-05-10", "P2", 5),
        ("2026-06-30", "P2", 5),
    ]
)


def test_a_forecast_quantity_is_used_ahead_of_trailing_sales():
    estimates = build_demand_estimates(
        ROWS,
        forecaster=forecaster_returning(
            FakeForecast("P1", 44.0, "forecastable"),
        ),
    )

    assert estimates["P1"].expected_units == 44.0
    assert estimates["P1"].source is DemandSource.PRODUCT_FORECAST
    assert estimates["P1"].period_start == AHEAD_START
    assert estimates["P1"].period_end == AHEAD_END


def test_a_product_the_forecast_cannot_cover_uses_its_own_recent_sales():
    estimates = build_demand_estimates(
        ROWS,
        forecaster=forecaster_returning(
            FakeForecast("P1", 44.0, "forecastable"),
            FakeForecast("P2", None, REASON_INSUFFICIENT_HISTORY),
        ),
    )

    assert estimates["P2"].expected_units == 5.0
    assert estimates["P2"].source is DemandSource.TRAILING_SALES


def test_a_product_with_neither_carries_the_forecast_s_reason():
    estimates = build_demand_estimates(
        ROWS,
        forecaster=forecaster_returning(
            FakeForecast("P9", None, REASON_NO_SALES_HISTORY),
        ),
    )

    assert estimates["P9"].expected_units is None
    assert estimates["P9"].unavailable_reason == REASON_NO_SALES_HISTORY


def test_products_the_forecast_never_mentions_still_get_an_estimate():
    estimates = build_demand_estimates(
        ROWS,
        forecaster=forecaster_returning(
            FakeForecast("P1", 44.0, "forecastable"),
        ),
    )

    assert estimates["P2"].source is DemandSource.TRAILING_SALES


def test_no_forecast_installed_falls_back_to_trailing_sales():
    def no_forecaster():
        return None

    estimates = build_demand_estimates(ROWS, forecaster=None)

    # The real module is not on main yet, so this exercises the same path the
    # loader takes when the import fails.
    for estimate in estimates.values():
        assert estimate.source is DemandSource.TRAILING_SALES


def test_a_failing_forecast_costs_accuracy_and_nothing_else():
    estimates = build_demand_estimates(ROWS, forecaster=failing_forecaster)

    assert estimates["P1"].expected_units == 20.0
    assert estimates["P1"].source is DemandSource.TRAILING_SALES
    assert estimates["P2"].source is DemandSource.TRAILING_SALES


def test_the_forecast_period_is_the_one_the_forecaster_gave():
    estimates = build_demand_estimates(
        ROWS,
        forecaster=forecaster_returning(
            FakeForecast(
                "P1",
                12.0,
                "forecastable",
                forecast_period_start=date(2026, 8, 1),
                forecast_period_end=date(2026, 8, 31),
            ),
        ),
    )

    assert estimates["P1"].period_start == date(2026, 8, 1)
    assert estimates["P1"].period_end == date(2026, 8, 31)


def test_a_forecast_answering_with_the_wrong_shape_costs_only_accuracy():
    """The forecaster is not merged yet, so its shape is not guaranteed."""

    def wrong_shape(df, frequency):
        return {"forecasts": [{"product_id": "P1"}]}

    estimates = build_demand_estimates(ROWS, forecaster=wrong_shape)

    assert estimates["P1"].source is DemandSource.TRAILING_SALES
    assert estimates["P2"].source is DemandSource.TRAILING_SALES


def test_a_forecast_returning_nothing_at_all_costs_only_accuracy():
    estimates = build_demand_estimates(ROWS, forecaster=lambda df, f: None)

    assert estimates["P1"].source is DemandSource.TRAILING_SALES


def test_a_plain_enum_status_is_recorded_by_its_value():
    """A StrEnum stringifies to its value; a plain Enum would not."""
    import enum

    class Status(enum.Enum):
        NO_SALES_HISTORY = "no_sales_history"

    estimates = build_demand_estimates(
        ROWS,
        forecaster=forecaster_returning(
            FakeForecast("P9", None, Status.NO_SALES_HISTORY),
        ),
    )

    assert estimates["P9"].unavailable_reason == "no_sales_history"
