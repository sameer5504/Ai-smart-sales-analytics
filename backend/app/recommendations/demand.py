"""Expected demand per product, used to size restocking advice (US-4.3.5).

Wraps the product-level sales forecast (US-3.1.1, app.sales_forecasting) in the
shape the recommendation rules need, and falls back to trailing sales when a
product cannot be forecast.

The forecaster returns every product in one call, so estimates are built once
per request and rules are handed a lookup rather than calling the forecast
themselves.

The forecast is optional. Until app.sales_forecasting is merged, and for any
product it cannot cover, estimates come from trailing sales instead, and each
estimate says which of the two it came from.
"""

from __future__ import annotations

import logging
import warnings
from datetime import date
from statistics import median
from typing import Callable, Protocol

import pandas as pd
from pydantic import BaseModel, ConfigDict

from app.recommendations.contract import DemandSource

logger = logging.getLogger(__name__)

# Restocking advice is sized for the month ahead, matching the revenue
# forecast. Anomaly detection runs weekly, so the two use different periods on
# purpose and each result states the period it covers.
DEFAULT_FREQUENCY = "monthly"

# Reasons a product has no forecast, mapped from the forecaster's status plus
# the case where a product does not appear in its output at all.
REASON_INSUFFICIENT_HISTORY = "insufficient_history"
REASON_NO_SALES_HISTORY = "no_sales_history"
REASON_NOT_IN_HISTORY = "not_in_history"

# Pandas period codes for the frequencies this module supports.
PERIOD_CODES = {"monthly": "M", "weekly": "W-SUN"}

# How many finished periods the trailing estimate looks back over. Three is
# enough for a median to have a middle value while still following a product
# that is genuinely changing.
TRAILING_PERIODS = 3

# What a trailing estimate needs from the prepared rows.
TRAILING_COLUMNS = ["transaction_date", "product_id", "quantity"]


class DemandEstimate(BaseModel):
    """How many units of a product are expected to sell in the next period.

    Attributes:
        expected_units: the estimate. None when neither the forecast nor the
            trailing history supports one.
        source: whether the estimate came from the product forecast or from
            trailing sales, so a rule can tell the user which was used.
        period_start: first day of the period the estimate covers.
        period_end: last day of the period the estimate covers.
        unavailable_reason: why the forecast could not be used.
    """

    model_config = ConfigDict(frozen=True)

    expected_units: float | None = None
    source: DemandSource | None = None
    period_start: date | None = None
    period_end: date | None = None
    unavailable_reason: str | None = None

    @property
    def is_available(self) -> bool:
        return self.expected_units is not None


# Returned for a product the forecaster did not cover and trailing sales
# cannot rescue, so a lookup always yields an estimate rather than raising.
UNAVAILABLE = DemandEstimate(unavailable_reason=REASON_NOT_IN_HISTORY)


class DemandEstimator(Protocol):
    """The callable shape rules depend on.

    Rules ask for one product and the estimator closes over the data, so a
    rule never touches the DataFrame or the forecast itself. A test injects a
    fixed estimate by passing any callable of this shape.
    """

    def __call__(self, product_id: str) -> DemandEstimate: ...


def _parse_dates(values: pd.Series) -> pd.Series:
    """Read transaction dates without losing rows to how they were written.

    Dates are parsed per value rather than against one inferred format, the
    same way the pipeline reads them, so a file mixing formats keeps every row.

    A file exported with UTC offsets is read at its own wall-clock time, which
    is the time the sale happened as far as the business is concerned. Rows
    carrying different offsets cannot share a column, and pandas signals that
    differently across versions: some raise, some hand back an object column.
    Both are recognised by the result not being dates, and the column is then
    read as UTC, which shifts a late-evening sale by a few hours rather than
    dropping it.
    """
    parsed = None

    with warnings.catch_warnings():
        # Mixed offsets warn here on some versions and raise on others. The
        # check below handles the outcome either way.
        warnings.simplefilter("ignore", FutureWarning)

        try:
            parsed = pd.to_datetime(values, errors="coerce", format="mixed")

        except (TypeError, ValueError):
            parsed = None

    if parsed is None or not pd.api.types.is_datetime64_any_dtype(parsed):
        parsed = pd.to_datetime(
            values,
            errors="coerce",
            format="mixed",
            utc=True,
        )

    if isinstance(parsed.dtype, pd.DatetimeTZDtype):
        return parsed.dt.tz_localize(None)

    return parsed


def _as_product_id(values: pd.Series) -> pd.Series:
    """Read product ids as text without turning 12345 into "12345.0".

    A product_id column with any blank cell is read as a float, and converting
    that straight to text would key every estimate under a spelling no other
    part of the application uses.
    """
    if pd.api.types.is_float_dtype(values):
        whole_numbers = values.round().astype("Int64")
        is_whole = values.notna() & (values == whole_numbers)

        text = values.astype("string")
        return text.where(~is_whole, whole_numbers.astype("string")).str.strip()

    return values.astype("string").str.strip()


def _period_units(
    df: pd.DataFrame,
    code: str,
) -> tuple[pd.Series, pd.Series, pd.Period] | None:
    """Return units per product per period, each product's first period, and
    the last period the data covers in full.

    Rows without a date, a product or a quantity are dropped, because a line
    item missing any of the three says nothing about how much of a product
    sells.

    Returns:
        A tuple of (units, first_period, complete_through), or None when the
        frame has nothing usable in it.
    """
    if df.empty or any(column not in df.columns for column in TRAILING_COLUMNS):
        return None

    rows = df[TRAILING_COLUMNS].copy()

    rows["transaction_date"] = _parse_dates(rows["transaction_date"])
    rows["quantity"] = pd.to_numeric(rows["quantity"], errors="coerce")
    rows["product_id"] = _as_product_id(rows["product_id"])

    rows = rows.dropna(subset=TRAILING_COLUMNS)
    rows = rows[rows["product_id"] != ""]

    if rows.empty:
        return None

    rows["period"] = rows["transaction_date"].dt.to_period(code)

    last_period = rows["period"].max()

    # An upload usually stops partway through the current month, and counting
    # that stub as a whole period would drag every estimate down. It is left
    # out unless the data reaches the end of it.
    reaches_the_end = rows["transaction_date"].max() >= last_period.end_time.normalize()
    complete_through = last_period if reaches_the_end else last_period - 1

    first_period = rows.groupby("product_id")["period"].min()

    units = rows[rows["period"] <= complete_through].groupby(["product_id", "period"])["quantity"].sum()

    return units, first_period, complete_through


def build_trailing_sales_estimates(
    df: pd.DataFrame,
    frequency: str = DEFAULT_FREQUENCY,
) -> dict[str, DemandEstimate]:
    """Return an estimate per product from its own recent sales.

    This is the fallback for a product the forecast cannot cover, and it is
    also usable on its own, which is why it does not import the forecast.

    Each product's units are totalled per period. The final period is left out
    when the data stops partway through it. The estimate is the median of the
    last few finished periods, counted only from the product's first sale
    onwards, so a product that launched last month is not judged against
    months it did not exist in. A finished period with no sales counts as
    zero, because a month a product did not sell in is a month of no demand
    rather than a month with nothing to say.

    The median is used rather than the average so that one promotion or one
    stockout does not set the restocking quantity on its own.

    Args:
        df: prepared rows from data_pipeline.preparation.load_cleaned.
        frequency: the period to estimate for, "monthly" or "weekly".

    Returns:
        A mapping of product_id to DemandEstimate, covering the period after
        the last finished one. Products the data cannot support are present
        with an unavailable_reason; products absent from the data are absent
        from the mapping, so use ``lookup`` to read it.

    Raises:
        ValueError: if the frequency is not one this module supports.
    """
    code = PERIOD_CODES.get(frequency)

    if code is None:
        raise ValueError(f"Unsupported frequency {frequency!r}. Expected one of {sorted(PERIOD_CODES)}.")

    counted = _period_units(df, code)

    if counted is None:
        return {}

    units, first_period, complete_through = counted

    window = pd.period_range(
        end=complete_through,
        periods=TRAILING_PERIODS,
        freq=code,
    )

    ahead = complete_through + 1
    estimates: dict[str, DemandEstimate] = {}

    for product_id, first_seen in first_period.items():
        periods = [period for period in window if period >= first_seen]

        if not periods:
            # The product only appears in the period that was left out, so
            # there is no finished period to measure it over yet.
            estimates[str(product_id)] = DemandEstimate(
                unavailable_reason=REASON_INSUFFICIENT_HISTORY,
            )
            continue

        sold = [float(units.get((product_id, period), 0.0)) for period in periods]

        estimates[str(product_id)] = DemandEstimate(
            expected_units=max(float(median(sold)), 0.0),
            source=DemandSource.TRAILING_SALES,
            period_start=ahead.start_time.date(),
            period_end=ahead.end_time.date(),
        )

    return estimates


def _load_forecaster() -> Callable | None:
    """Return the product sales forecast, or None when it is not available.

    Imported here rather than at the top of the module because
    app.sales_forecasting lands separately (US-3.1.1). Until it does, and if it
    were ever removed, demand estimates fall back to trailing sales rather than
    the whole module failing to import.
    """
    try:
        from app.sales_forecasting.service import forecast_product_sales

    except ImportError:
        return None

    return forecast_product_sales


def _status_reason(status) -> str:
    """Return the forecaster's status as a plain string.

    A StrEnum stringifies to its value, but a plain Enum would give
    "ClassName.MEMBER", which is not something to show or store.
    """
    return str(getattr(status, "value", status))


def _from_forecast(forecast) -> DemandEstimate | None:
    """Turn one product's forecast into an estimate.

    Returns None when the forecaster could not produce a quantity, which is the
    signal to use that product's trailing sales instead.
    """
    if forecast.forecast_quantity is None:
        return None

    return DemandEstimate(
        expected_units=float(forecast.forecast_quantity),
        source=DemandSource.PRODUCT_FORECAST,
        period_start=forecast.forecast_period_start,
        period_end=forecast.forecast_period_end,
    )


def build_demand_estimates(
    df: pd.DataFrame,
    frequency: str = DEFAULT_FREQUENCY,
    forecaster: Callable | None = None,
) -> dict[str, DemandEstimate]:
    """Return an estimate per product, keyed by product_id.

    Calls the product-level sales forecast once for the whole frame and maps
    each result onto a DemandEstimate. A product the forecast could not cover
    falls back to its own trailing sales, so a rule gets a usable quantity for
    as many products as the data supports.

    The forecast is treated as optional. When it is not installed, or the call
    fails, every estimate comes from trailing sales and the result says so
    through its source field rather than pretending a forecast was used.

    Args:
        df: prepared rows from data_pipeline.preparation.load_cleaned.
        frequency: the forecast period, "monthly" or "weekly".
        forecaster: the forecast to call. Defaults to the real one, and takes
            a fake in tests.

    Returns:
        A mapping of product_id to DemandEstimate. Products missing from both
        the forecast output and the sales rows are absent from the mapping; use
        ``lookup`` to get an unavailable estimate for those instead of handling
        KeyError.
    """
    trailing = build_trailing_sales_estimates(df, frequency)

    if forecaster is None:
        forecaster = _load_forecaster()

    if forecaster is None:
        logger.info(
            "No product sales forecast available, estimating demand from trailing sales only",
        )
        return trailing

    # The call and the reading of its result are guarded together, because a
    # forecast that answers with the wrong shape breaks the restocking
    # suggestion just as thoroughly as one that raises.
    try:
        response = forecaster(df, frequency)

        estimates = dict(trailing)

        for forecast in response.forecasts:
            product_id = str(forecast.product_id)
            forecast_estimate = _from_forecast(forecast)

            if forecast_estimate is not None:
                estimates[product_id] = forecast_estimate
                continue

            # The forecast could not cover this product. Its own trailing
            # sales stand if there are any; otherwise the forecast's reason is
            # carried through, since it explains the gap better than a missing
            # key would.
            existing = estimates.get(product_id)

            if existing is None or not existing.is_available:
                estimates[product_id] = DemandEstimate(
                    unavailable_reason=_status_reason(forecast.forecast_status),
                )

        return estimates

    except Exception:
        # A broken forecast should cost accuracy, not the whole restocking
        # suggestion, and trailing sales is the fallback the rules already
        # understand.
        logger.exception(
            "Product sales forecast unusable, falling back to trailing sales",
        )
        return trailing


def lookup(estimates: dict[str, DemandEstimate]) -> DemandEstimator:
    """Return a DemandEstimator that reads from a prebuilt mapping.

    Products the forecast did not cover return UNAVAILABLE rather than raising,
    so a rule handles a missing estimate the same way it handles an
    unforecastable one.
    """

    def estimator(product_id: str) -> DemandEstimate:
        return estimates.get(product_id, UNAVAILABLE)

    return estimator
