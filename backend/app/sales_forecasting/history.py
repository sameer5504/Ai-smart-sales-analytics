from __future__ import annotations

import numbers

import pandas as pd

from app.sales_forecasting.schemas import ForecastFrequency

REQUIRED_FIELDS = {
    "transaction_date",
    "product_id",
    "quantity",
}


def _normalize_product_id(value: object) -> str:
    """
    Convert a product identifier to a stable string representation.

    CSV loading may turn numeric IDs into Python numbers. Integral numeric
    identifiers are converted without adding an artificial '.0'.
    """
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, numbers.Integral):
        return str(value)

    if isinstance(value, numbers.Real):
        numeric_value = float(value)

        if numeric_value.is_integer():
            return str(int(numeric_value))

        return str(value)

    return str(value).strip()


def _validate_input(data: pd.DataFrame) -> None:
    """Validate the minimum fields required for product sales forecasting."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            f"Expected a pandas DataFrame, got {type(data).__name__}"
        )

    missing = sorted(
        REQUIRED_FIELDS - set(data.columns)
    )

    if missing:
        raise ValueError(
            "Missing required forecasting field(s): "
            + ", ".join(missing)
        )


def _period_frequency(
    frequency: ForecastFrequency,
) -> str:
    if frequency == ForecastFrequency.WEEKLY:
        # Monday -> Sunday
        return "W-SUN"

    if frequency == ForecastFrequency.MONTHLY:
        return "M"

    raise ValueError(
        f"Unsupported forecast frequency: {frequency}"
    )


def _complete_period_window(
    dates: pd.Series,
    period_frequency: str,
) -> tuple[pd.Period, pd.Period] | None:
    """
    Return the first and last complete periods represented by the dataset.

    Partial boundary periods are excluded so forecasting history is not trained
    on an incomplete week or month.
    """
    minimum_date = dates.min()
    maximum_date = dates.max()

    if pd.isna(minimum_date) or pd.isna(maximum_date):
        return None

    minimum_date = pd.Timestamp(
        minimum_date
    ).normalize()

    maximum_date = pd.Timestamp(
        maximum_date
    ).normalize()

    first_period = minimum_date.to_period(
        period_frequency
    )

    last_period = maximum_date.to_period(
        period_frequency
    )

    if (
        minimum_date
        > first_period.start_time.normalize()
    ):
        first_complete_period = (
            first_period + 1
        )
    else:
        first_complete_period = (
            first_period
        )

    if (
        maximum_date
        < last_period.end_time.normalize()
    ):
        last_complete_period = (
            last_period - 1
        )
    else:
        last_complete_period = (
            last_period
        )

    if (
        first_complete_period
        > last_complete_period
    ):
        return None

    return (
        first_complete_period,
        last_complete_period,
    )


def build_product_sales_history(
    data: pd.DataFrame,
    frequency: ForecastFrequency,
) -> pd.DataFrame:
    """
    Build continuous product-level sales history from prepared sales rows.

    Signed quantities are summed within each period. A negative net period is
    retained in ``net_quantity`` for traceability, while the forecasting target
    is clipped at zero.

    Missing periods after a product's first observed complete period are
    inserted with zero quantity.
    """
    _validate_input(data)

    output_columns = [
        "product_id",
        "period",
        "period_start",
        "period_end",
        "net_quantity",
        "forecast_quantity",
        "transaction_rows",
        "was_observed",
    ]

    if data.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    working = data[
        [
            "transaction_date",
            "product_id",
            "quantity",
        ]
    ].copy()

    working["transaction_date"] = (
        pd.to_datetime(
            working["transaction_date"],
            errors="coerce",
        )
    )

    working["quantity"] = pd.to_numeric(
        working["quantity"],
        errors="coerce",
    )

    # Prepared pipeline data should already contain valid values,
    # but keep this feature safe when called independently in tests.
    working = working.dropna(
        subset=[
            "transaction_date",
            "product_id",
            "quantity",
        ]
    )

    if working.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    working["product_id"] = (
        working["product_id"]
        .map(_normalize_product_id)
    )

    working = working.loc[
        working["product_id"] != ""
    ].copy()

    if working.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    period_frequency = (
        _period_frequency(frequency)
    )

    complete_window = (
        _complete_period_window(
            working["transaction_date"],
            period_frequency,
        )
    )

    if complete_window is None:
        return pd.DataFrame(
            columns=output_columns
        )

    (
        first_complete_period,
        last_complete_period,
    ) = complete_window

    working["period"] = (
        working["transaction_date"]
        .dt.to_period(
            period_frequency
        )
    )

    working = working.loc[
        (
            working["period"]
            >= first_complete_period
        )
        & (
            working["period"]
            <= last_complete_period
        )
    ].copy()

    if working.empty:
        return pd.DataFrame(
            columns=output_columns
        )

    aggregated = (
        working.groupby(
            [
                "product_id",
                "period",
            ],
            as_index=False,
        )
        .agg(
            net_quantity=(
                "quantity",
                "sum",
            ),
            transaction_rows=(
                "quantity",
                "size",
            ),
        )
    )

    aggregated["forecast_quantity"] = (
        aggregated["net_quantity"]
        .clip(lower=0)
        .astype(float)
    )

    histories: list[pd.DataFrame] = []

    for (
        product_id,
        product_data,
    ) in aggregated.groupby(
        "product_id",
        sort=False,
    ):
        product_data = (
            product_data
            .sort_values("period")
            .set_index("period")
        )

        first_product_period = (
            product_data.index.min()
        )

        full_period_index = (
            pd.period_range(
                start=first_product_period,
                end=last_complete_period,
                freq=period_frequency,
            )
        )

        product_history = (
            product_data.reindex(
                full_period_index
            )
        )

        product_history.index.name = (
            "period"
        )

        product_history["product_id"] = (
            product_id
        )

        product_history[
            "net_quantity"
        ] = (
            product_history[
                "net_quantity"
            ]
            .fillna(0)
            .astype(float)
        )

        product_history[
            "forecast_quantity"
        ] = (
            product_history[
                "forecast_quantity"
            ]
            .fillna(0)
            .astype(float)
        )

        product_history[
            "transaction_rows"
        ] = (
            product_history[
                "transaction_rows"
            ]
            .fillna(0)
            .astype(int)
        )

        product_history["was_observed"] = (
            product_history[
                "transaction_rows"
            ]
            > 0
        )

        product_history = (
            product_history.reset_index()
        )

        product_history[
            "period_start"
        ] = (
            product_history["period"]
            .dt.start_time
            .dt.date
        )

        product_history[
            "period_end"
        ] = (
            product_history["period"]
            .dt.end_time
            .dt.date
        )

        histories.append(
            product_history
        )

    history = pd.concat(
        histories,
        ignore_index=True,
    )

    return history[
        output_columns
    ]
