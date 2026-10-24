"""Client for the AutoML forecasting model served on an Azure managed endpoint.

The endpoint model was trained on one UK retailer and forecasts revenue in that
retailer's own units. To serve any business from it, the uploaded series is scaled so its
trailing 28-day average matches the level the model trained at, the forecast is
requested, and the answer is divided back. That is exact for a difference in size.

The model runs behind HTTP rather than in this process because it needs Python 3.10 with
numpy 1.23, pandas 1.5 and scikit-learn 1.5, while this application runs Python 3.12 with
the versions its own LightGBM model requires. See docs/automl_benchmark.md.

Every failure path returns None so the caller can fall back to the local model.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from .trained_revenue_model import (
    BASELINE_WINDOW,
    MonthlyForecast,
    build_features,
    detect_closed_days,
)

logger = logging.getLogger(__name__)

ENDPOINT_URL = "AZURE_FORECAST_ENDPOINT"
ENDPOINT_KEY = "AZURE_FORECAST_KEY"

# Trailing 28-day average at the end of the series the endpoint model trained on.
# Uploaded series are scaled to this level before being sent.
TRAINING_BASELINE = 47789.20

# The endpoint was trained on a data asset built before weekday_ratio was added to
# build_features, so that column is dropped to match the schema it expects.
UNTRAINED_COLUMNS = ["weekday_ratio"]

YEAR_LAG = 364
REQUEST_TIMEOUT_SECONDS = 20

# A managed endpoint serves one request per instance by default and answers 429 to
# anything arriving alongside it. A page that asks for the forecast more than once
# would otherwise drop to the local model for no better reason than timing, so a
# rejected request is retried briefly before giving up.
RETRY_STATUSES = {429, 503}
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.4


def is_configured() -> bool:
    """True when both the endpoint URL and its key are set."""
    return bool(os.environ.get(ENDPOINT_URL) and os.environ.get(ENDPOINT_KEY))


def _endpoint_frame(dates: pd.DatetimeIndex, history: pd.Series, country: str) -> pd.DataFrame:
    """The columns the endpoint's training asset carried, for the given dates.

    ``lag364`` is the raw value a year earlier rather than a ratio, matching the asset.
    """
    baseline = float(history.iloc[-BASELINE_WINDOW:].mean())
    frame = build_features(dates, history, baseline, country, detect_closed_days(history))
    frame = frame.drop(columns=UNTRAINED_COLUMNS + ["lag364_ratio"])
    frame[f"lag{YEAR_LAG}"] = [history.get(day - pd.Timedelta(days=YEAR_LAG), np.nan) for day in dates]
    frame.insert(0, "date", dates.strftime("%Y-%m-%d"))
    return frame.reset_index(drop=True)


def _post(payload: dict) -> dict | list:
    request = urllib.request.Request(
        os.environ[ENDPOINT_URL],
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ[ENDPOINT_KEY]}",
        },
    )

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read().decode()
            break
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUSES or attempt == RETRY_ATTEMPTS:
                raise
            logger.info(
                "AutoML endpoint answered %d, retrying (%d of %d)",
                error.code,
                attempt,
                RETRY_ATTEMPTS - 1,
            )
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    parsed = json.loads(body)
    return json.loads(parsed) if isinstance(parsed, str) else parsed


def _predictions(response: dict | list) -> list[float]:
    """Pull the forecast values out of whatever shape the endpoint returns."""
    if isinstance(response, dict):
        for key in ("forecast", "predictions", "result", "output"):
            if key in response:
                response = response[key]
                break
    if isinstance(response, dict):
        raise ValueError(f"no forecast values in response keys {list(response)}")
    return [float(value) for value in response]


def forecast_next_month(daily: pd.Series, country: str = "GB") -> MonthlyForecast | None:
    """Forecast the month after the series ends, or None if the endpoint cannot answer."""
    if not is_configured():
        return None

    baseline = float(daily.iloc[-BASELINE_WINDOW:].mean())
    if not np.isfinite(baseline) or baseline <= 0:
        return None

    scale = TRAINING_BASELINE / baseline
    scaled = daily * scale

    start = (daily.index.max() + pd.offsets.MonthBegin(1)).normalize()
    days = pd.date_range(start, start + pd.offsets.MonthEnd(0), freq="D")
    frame = _endpoint_frame(days, scaled, country)

    payload = {
        "input_data": {
            "columns": list(frame.columns),
            "index": list(range(len(frame))),
            "data": frame.where(pd.notna(frame), None).values.tolist(),
        }
    }

    try:
        values = _predictions(_post(payload))
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as error:
        logger.warning("AutoML endpoint unavailable, falling back to the local model: %s", error)
        return None

    if len(values) != len(days):
        logger.warning("AutoML endpoint returned %d values for %d days, falling back", len(values), len(days))
        return None

    predicted = np.clip(np.asarray(values, dtype=float), 0, None) / scale
    daily_prediction = pd.Series(predicted, index=days, name="revenue")
    return MonthlyForecast(
        target_month=start.strftime("%Y-%m"),
        predicted_revenue=float(daily_prediction.sum()),
        daily=daily_prediction,
    )
