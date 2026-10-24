from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.anomaly.schemas import (
    Anomaly,
    AnomalyMetric,
    AnomalyScope,
    AnomalyType,
)
from app.data_pipeline.cleaning.deduplication import remove_exact_duplicates
from app.services.anomaly_severity import (
    classify_anomaly_severity,
)


@dataclass(frozen=True)
class ProductAnomalyConfig:
    """Configurable MVP rules for product-level anomaly detection."""

    history_periods: int = 4
    sharp_drop_percent: float = 50.0
    unusual_increase_percent: float = 100.0
    dead_stock_periods: int = 4
    min_baseline_units: float = 5.0
    min_active_history_periods: int = 2
    weekly_frequency: str = "W-SUN"


DEFAULT_PRODUCT_ANOMALY_CONFIG = ProductAnomalyConfig()

_REQUIRED_COLUMNS = {
    "transaction_date",
    "order_id",
    "product_id",
    "product_name",
    "quantity",
    "unit_price",
}


@dataclass(frozen=True)
class _DetectionContext:
    weekly_units: pd.DataFrame
    active_periods: list[pd.Period]
    first_sale_period: dict[str, pd.Period]
    product_names: dict[str, str | None]


def _prepare_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(sales_df, pd.DataFrame):
        raise TypeError("sales_df must be a pandas DataFrame")

    missing = sorted(_REQUIRED_COLUMNS - set(sales_df.columns))
    if missing:
        raise ValueError(f"Missing required sales columns: {missing}")

    clean = remove_exact_duplicates(sales_df).dataframe.copy()

    clean["transaction_date"] = pd.to_datetime(clean["transaction_date"], errors="coerce")
    clean["quantity"] = pd.to_numeric(clean["quantity"], errors="coerce")
    clean["unit_price"] = pd.to_numeric(clean["unit_price"], errors="coerce")

    clean["product_id"] = clean["product_id"].astype("string").str.strip()
    clean["product_name"] = clean["product_name"].astype("string").str.strip()
    clean["order_id"] = clean["order_id"].astype("string").str.strip()

    clean = clean.dropna(
        subset=[
            "transaction_date",
            "order_id",
            "product_id",
            "quantity",
            "unit_price",
        ]
    )

    clean = clean[(clean["product_id"] != "") & (clean["quantity"] > 0) & (clean["unit_price"] > 0)].copy()

    return clean.reset_index(drop=True)


def _build_context(
    sales_df: pd.DataFrame,
    config: ProductAnomalyConfig,
) -> _DetectionContext | None:
    clean = _prepare_sales(sales_df)

    if clean.empty:
        return None

    clean["period"] = clean["transaction_date"].dt.to_period(config.weekly_frequency)

    store_units = clean.groupby("period")["quantity"].sum().sort_index()

    active_periods = list(store_units[store_units > 0].index)

    if not active_periods:
        return None

    grouped = (
        clean.groupby(["product_id", "period"])["quantity"]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(columns=active_periods, fill_value=0.0)
        .sort_index()
    )

    first_sale_period = clean.groupby("product_id")["period"].min().to_dict()

    product_names: dict[str, str | None] = {}

    for product_id, group in clean.groupby("product_id", sort=False):
        group_by_date = group.sort_values("transaction_date")
        names = group_by_date["product_name"].dropna()

        product_names[str(product_id)] = str(names.iloc[-1]) if not names.empty else None

    grouped.index = grouped.index.astype(str)

    first_sale_period = {str(product_id): period for product_id, period in first_sale_period.items()}

    return _DetectionContext(
        weekly_units=grouped,
        active_periods=active_periods,
        first_sale_period=first_sale_period,
        product_names=product_names,
    )


def _period_dates(period: pd.Period) -> tuple:
    return period.start_time.date(), period.end_time.date()


def _change_percent(
    current: float,
    baseline: float,
) -> float:
    return ((current - baseline) / baseline) * 100.0


def _eligible_periods_for_product(
    context: _DetectionContext,
    product_id: str,
) -> list[pd.Period]:
    first_period = context.first_sale_period[product_id]

    return [period for period in context.active_periods if period >= first_period]


def _history_values(
    context: _DetectionContext,
    product_id: str,
    periods: list[pd.Period],
) -> pd.Series:
    return context.weekly_units.loc[
        product_id,
        periods,
    ].astype(float)


def _detect_dead_stock_from_context(
    context: _DetectionContext,
    config: ProductAnomalyConfig,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    for product_id in context.weekly_units.index:
        periods = _eligible_periods_for_product(
            context,
            product_id,
        )

        if len(periods) <= config.dead_stock_periods:
            continue

        zero_window = periods[-config.dead_stock_periods :]

        zero_values = _history_values(
            context,
            product_id,
            zero_window,
        )

        if not (zero_values == 0).all():
            continue

        prior_periods = periods[: -config.dead_stock_periods]

        prior_values = _history_values(
            context,
            product_id,
            prior_periods,
        )

        positive_prior = prior_values[prior_values > 0]

        if len(positive_prior) < config.min_active_history_periods:
            continue

        baseline_values = positive_prior.tail(config.history_periods)

        baseline = float(baseline_values.median())

        period_start = zero_window[0].start_time.date()
        period_end = zero_window[-1].end_time.date()

        anomalies.append(
            Anomaly(
                anomaly_type=AnomalyType.DEAD_STOCK,
                scope=AnomalyScope.PRODUCT,
                metric=AnomalyMetric.UNITS_SOLD,
                severity=classify_anomaly_severity(
                    AnomalyType.DEAD_STOCK,
                    -100.0,
                ),
                product_id=product_id,
                product_name=context.product_names.get(product_id),
                period_start=period_start,
                period_end=period_end,
                current_value=0.0,
                baseline_value=baseline,
                change_percent=-100.0 if baseline > 0 else None,
                message=(
                    f"Product {product_id} recorded zero "
                    f"units sold for "
                    f"{config.dead_stock_periods} "
                    f"consecutive active weeks."
                ),
            )
        )

    return anomalies


def _detect_change_from_context(
    context: _DetectionContext,
    config: ProductAnomalyConfig,
    anomaly_type: AnomalyType,
) -> list[Anomaly]:
    anomalies: list[Anomaly] = []

    for product_id in context.weekly_units.index:
        periods = _eligible_periods_for_product(
            context,
            product_id,
        )

        if len(periods) < config.history_periods + 1:
            continue

        current_period = periods[-1]

        history_periods = periods[-(config.history_periods + 1) : -1]

        history = _history_values(
            context,
            product_id,
            history_periods,
        )

        if int((history > 0).sum()) < config.min_active_history_periods:
            continue

        baseline = float(history.median())

        if baseline < config.min_baseline_units:
            continue

        current = float(
            context.weekly_units.loc[
                product_id,
                current_period,
            ]
        )

        change = _change_percent(
            current,
            baseline,
        )

        if anomaly_type == AnomalyType.SHARP_DROP:
            is_anomaly = change <= -config.sharp_drop_percent

            threshold_text = f"-{config.sharp_drop_percent:g}%"

        elif anomaly_type == AnomalyType.UNUSUAL_INCREASE:
            is_anomaly = change >= config.unusual_increase_percent

            threshold_text = f"+{config.unusual_increase_percent:g}%"

        else:
            raise ValueError(f"Unsupported change anomaly type: {anomaly_type}")

        if not is_anomaly:
            continue

        period_start, period_end = _period_dates(current_period)

        direction = "decreased" if change < 0 else "increased"

        anomalies.append(
            Anomaly(
                anomaly_type=anomaly_type,
                scope=AnomalyScope.PRODUCT,
                metric=AnomalyMetric.UNITS_SOLD,
                severity=classify_anomaly_severity(
                    anomaly_type,
                    change,
                ),
                product_id=product_id,
                product_name=context.product_names.get(product_id),
                period_start=period_start,
                period_end=period_end,
                current_value=current,
                baseline_value=baseline,
                change_percent=round(change, 2),
                message=(
                    f"Product {product_id} units sold "
                    f"{direction} by "
                    f"{abs(change):.2f}% versus its "
                    f"recent baseline "
                    f"(threshold {threshold_text})."
                ),
            )
        )

    return anomalies


def detect_sharp_drops(
    sales_df: pd.DataFrame,
    config: ProductAnomalyConfig = (DEFAULT_PRODUCT_ANOMALY_CONFIG),
) -> list[Anomaly]:
    context = _build_context(
        sales_df,
        config,
    )

    if context is None:
        return []

    return _detect_change_from_context(
        context,
        config,
        AnomalyType.SHARP_DROP,
    )


def detect_dead_stock(
    sales_df: pd.DataFrame,
    config: ProductAnomalyConfig = (DEFAULT_PRODUCT_ANOMALY_CONFIG),
) -> list[Anomaly]:
    context = _build_context(
        sales_df,
        config,
    )

    if context is None:
        return []

    return _detect_dead_stock_from_context(
        context,
        config,
    )


def detect_unusual_increases(
    sales_df: pd.DataFrame,
    config: ProductAnomalyConfig = (DEFAULT_PRODUCT_ANOMALY_CONFIG),
) -> list[Anomaly]:
    context = _build_context(
        sales_df,
        config,
    )

    if context is None:
        return []

    return _detect_change_from_context(
        context,
        config,
        AnomalyType.UNUSUAL_INCREASE,
    )


def detect_product_anomalies(
    sales_df: pd.DataFrame,
    config: ProductAnomalyConfig = (DEFAULT_PRODUCT_ANOMALY_CONFIG),
) -> list[Anomaly]:
    """
    Return current product-level anomalies
    using one shared engine.
    """

    context = _build_context(
        sales_df,
        config,
    )

    if context is None:
        return []

    dead_stock = _detect_dead_stock_from_context(
        context,
        config,
    )

    dead_stock_ids = {anomaly.product_id for anomaly in dead_stock}

    sharp_drops = [
        anomaly
        for anomaly in _detect_change_from_context(
            context,
            config,
            AnomalyType.SHARP_DROP,
        )
        if anomaly.product_id not in dead_stock_ids
    ]

    unusual_increases = _detect_change_from_context(
        context,
        config,
        AnomalyType.UNUSUAL_INCREASE,
    )

    return sorted(
        dead_stock + sharp_drops + unusual_increases,
        key=lambda anomaly: (
            anomaly.product_id,
            anomaly.anomaly_type.value,
        ),
    )
