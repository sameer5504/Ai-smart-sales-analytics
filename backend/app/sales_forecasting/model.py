from __future__ import annotations

import numpy as np

from app.sales_forecasting.schemas import ForecastStatus

MODEL_NAME = "moving_average_3"
MODEL_WINDOW = 3


def moving_average_3(
    values: list[float] | np.ndarray,
) -> float | None:
    """
    Forecast the next period using the mean
    of the last three available periods.

    If fewer than three historical periods exist,
    the available periods are used.

    Returns None when no history exists.
    """
    values_array = np.asarray(
        values,
        dtype=float,
    )

    if len(values_array) == 0:
        return None

    recent_values = (
        values_array[-MODEL_WINDOW:]
    )

    prediction = float(
        np.mean(recent_values)
    )

    return max(
        0.0,
        prediction,
    )


def classify_history(
    nonzero_periods: int,
) -> ForecastStatus:
    """
    Determine whether a product has enough
    real sales history to expose a forecast.

    Policy:
      0 non-zero periods -> no_sales_history
      1-2 periods         -> insufficient_history
      3+ periods          -> forecastable
    """
    if nonzero_periods < 0:
        raise ValueError(
            "nonzero_periods must be non-negative."
        )

    if nonzero_periods == 0:
        return ForecastStatus.NO_SALES_HISTORY

    if nonzero_periods < MODEL_WINDOW:
        return (
            ForecastStatus.INSUFFICIENT_HISTORY
        )

    return ForecastStatus.FORECASTABLE


def forecast_from_history(
    values: list[float] | np.ndarray,
) -> tuple[
    ForecastStatus,
    float | None,
]:
    """
    Classify the available sales history and,
    when sufficient, return the MA(3) forecast.
    """
    values_array = np.asarray(
        values,
        dtype=float,
    )

    nonzero_periods = int(
        np.sum(
            values_array > 0
        )
    )

    status = classify_history(
        nonzero_periods
    )

    if (
        status
        != ForecastStatus.FORECASTABLE
    ):
        return (
            status,
            None,
        )

    return (
        status,
        moving_average_3(
            values_array
        ),
    )
