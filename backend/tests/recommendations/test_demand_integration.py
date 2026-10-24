"""Demand estimates against the real product sales forecast (US-3.1.1).

app.sales_forecasting is not on main yet, so every test here is skipped for
now. They start running on the first build after that module merges, which is
where a change to its output contract would show up. The unit tests in
test_demand_forecast.py cover the same logic against a fake and run today.
"""

import pandas as pd
import pytest

pytest.importorskip(
    "app.sales_forecasting.service",
    reason="The product sales forecast has not been merged yet (US-3.1.1).",
)

from app.recommendations.contract import DemandSource  # noqa: E402
from app.recommendations.demand import (  # noqa: E402
    _load_forecaster,
    build_demand_estimates,
)


def steady_sales() -> pd.DataFrame:
    """Six finished months for one product, enough for any moving average."""
    return pd.DataFrame(
        [(f"2026-0{month}-10", "P1", 20.0) for month in range(1, 7)] + [("2026-06-30", "P1", 0.0)],
        columns=["transaction_date", "product_id", "quantity"],
    )


def test_the_real_forecaster_is_found():
    assert _load_forecaster() is not None


def test_a_forecastable_product_is_estimated_from_the_forecast():
    estimates = build_demand_estimates(steady_sales())

    assert "P1" in estimates
    assert estimates["P1"].source is DemandSource.PRODUCT_FORECAST
    assert estimates["P1"].expected_units is not None


def test_a_product_with_almost_no_history_still_gets_an_estimate():
    rows = pd.DataFrame(
        [
            ("2026-05-10", "P2", 7.0),
            ("2026-06-30", "P2", 9.0),
        ],
        columns=["transaction_date", "product_id", "quantity"],
    )

    estimates = build_demand_estimates(rows)

    # Either the forecaster covered it or trailing sales did. What matters is
    # that a rule is never handed a missing product.
    assert "P2" in estimates
    assert estimates["P2"].source is not None or estimates["P2"].unavailable_reason


def test_every_estimate_names_where_it_came_from():
    estimates = build_demand_estimates(steady_sales())

    for estimate in estimates.values():
        if estimate.is_available:
            assert estimate.source in {
                DemandSource.PRODUCT_FORECAST,
                DemandSource.TRAILING_SALES,
            }
        else:
            assert estimate.unavailable_reason
