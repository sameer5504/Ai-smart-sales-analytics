"""Serve the revenue forecast behind the forecast contract.

Two models can answer. The AutoML endpoint is used when it is configured and reachable,
and the trained artifact in this repository answers otherwise, so a forecast is always
available and the response says which produced it. See app/forecast/automl_endpoint.py
and docs/automl_benchmark.md.

Each request supplies its own series, from which the recent baseline, rest days, and
(via region) the holiday calendar are derived.

The artifact is read from ``REVENUE_MODEL_PATH`` when that is set, and otherwise from
``models/revenue_model.joblib`` under the backend directory. That fallback is built
from this file's own location rather than the working directory: App Service extracts
the application into a generated directory at container start, so the process's
working directory is not the application root and a relative path resolves somewhere
unpredictable.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from app.forecast import automl_endpoint
from app.forecast.contract import (
    MODEL_AUTOML,
    MODEL_TRAINED,
    REASON_INSUFFICIENT_HISTORY,
    REASON_MODEL_UNAVAILABLE,
    ForecastResult,
)
from app.forecast.daily_series import build_daily_revenue_series
from app.forecast.evaluation import MIN_HISTORY_MONTHS
from app.forecast.monthly import history_points, monthly_totals, next_month_start
from app.forecast.trained_revenue_model import BASELINE_WINDOW, TrainedRevenueModel

logger = logging.getLogger(__name__)

MODEL_PATH_ENV = "REVENUE_MODEL_PATH"

# app/forecast/service.py -> the backend directory holding models/.
BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = BACKEND_DIR / "models" / "revenue_model.joblib"

# Three complete months is the minimum. The backtest in the analysis notebook measures
# the model at every history length: one month gives a forecast near zero, two months
# roughly doubles the error, and from three months on it is flat at about 17% MAPE.
# A shorter series clears the 28-day baseline window but does not produce a usable
# forecast, so it is reported as unavailable rather than answered badly.
MIN_MONTHS = MIN_HISTORY_MONTHS
MIN_DAYS = BASELINE_WINDOW  # the baseline window still has to be covered and positive

MODEL_UNAVAILABLE_MESSAGE = "The revenue forecasting model is not available on this server."

# Coarse region -> a representative country for the holiday calendar. A stand-in
# until accounts carry a specific country (e.g. a Palestinian business should use PS
# rather than the region default).
REGION_TO_COUNTRY = {"europe": "GB", "middle_east": "SA", "us": "US"}
DEFAULT_COUNTRY = "GB"

_cache: dict[str, TrainedRevenueModel] = {}


def resolve_model_path(model_path: str | None = None) -> str:
    """Return the path to load the trained model from.

    An explicit argument wins, then ``REVENUE_MODEL_PATH``, then the copy kept in
    the backend's ``models`` directory. Only the last of those is derived from
    this file's location; a configured path is used exactly as given, so a
    deployment can point at a model anywhere on its filesystem.
    """
    if model_path:
        return model_path

    return os.environ.get(MODEL_PATH_ENV) or str(DEFAULT_MODEL_PATH)


def _load(path: str) -> TrainedRevenueModel:
    if path not in _cache:
        _cache[path] = TrainedRevenueModel.load(path)
    return _cache[path]


def _target_month(series: pd.Series, monthly: pd.Series) -> str:
    """The month this endpoint forecasts, as "YYYY-MM".

    The month after the last day of data, which is what the trained model produces.
    Deriving it from the last *complete* month instead would disagree with the model
    whenever the data stops mid-month: rows ending on the 9th would report the
    part-elapsed month while the model returned the one after it, so an available
    response and an unavailable one would name different months for the same upload.
    """
    if len(series) == 0:
        return next_month_start(monthly, series).strftime("%Y-%m")
    return (series.index.max() + pd.offsets.MonthBegin(1)).strftime("%Y-%m")


def forecast_from_dataframe(
    df: pd.DataFrame,
    *,
    region: str | None = None,
    country: str | None = None,
    model_path: str | None = None,
) -> ForecastResult:
    """Forecast next month's revenue for the records in ``df`` using the trained model."""
    series = build_daily_revenue_series(df).series
    monthly = monthly_totals(series)
    history = history_points(monthly)
    target_month = _target_month(series, monthly)

    if len(monthly) < MIN_MONTHS:
        return ForecastResult.unavailable(
            target_month=target_month,
            reason=REASON_INSUFFICIENT_HISTORY,
            message=(f"Need at least {MIN_MONTHS} complete months of sales history to forecast; found {len(monthly)}."),
            history=history,
        )

    # The model scales its forecast against the recent baseline, so a window that
    # nets zero or negative (a closed store, or returns above sales) has no scale.
    if float(series.iloc[-MIN_DAYS:].mean()) <= 0:
        return ForecastResult.unavailable(
            target_month=target_month,
            reason=REASON_INSUFFICIENT_HISTORY,
            message=f"No positive revenue in the last {MIN_DAYS} days, so there is no baseline to forecast against.",
            history=history,
        )

    resolved_country = country or REGION_TO_COUNTRY.get(region, DEFAULT_COUNTRY)

    # The AutoML endpoint is preferred when it is configured and reachable. It returns
    # None on any failure, including not being configured at all, so the local artifact
    # below stays the answer whenever the endpoint cannot give one.
    served = automl_endpoint.forecast_next_month(series, country=resolved_country)
    if served is not None:
        return ForecastResult.available(
            target_month=served.target_month,
            predicted_revenue=served.predicted_revenue,
            model=MODEL_AUTOML,
            history=history,
        )

    path = resolve_model_path(model_path)

    try:
        model = _load(path)
    except OSError as exc:
        # The artifact is committed, so this means a deployment did not carry it
        # across. Report it as an unavailable forecast the caller can show, rather
        # than failing the request.
        logger.error("Could not load the revenue model from %s: %s", path, exc)
        return ForecastResult.unavailable(
            target_month=target_month,
            reason=REASON_MODEL_UNAVAILABLE,
            message=MODEL_UNAVAILABLE_MESSAGE,
            history=history,
        )

    forecast = model.forecast_next_month(series, country=resolved_country)
    return ForecastResult.available(
        target_month=forecast.target_month,
        predicted_revenue=forecast.predicted_revenue,
        model=MODEL_TRAINED,
        history=history,
    )
