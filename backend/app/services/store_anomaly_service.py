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
class StoreAnomalyConfig:
    """Configurable MVP rules for store-level anomaly detection."""

    history_periods: int = 4
    sharp_drop_percent: float = 50.0
    unusual_increase_percent: float = 100.0
    seasonal_tolerance_percent: float = 20.0
    min_seasonal_history_periods: int = 2
    weekly_frequency: str = "W-SUN"


DEFAULT_STORE_ANOMALY_CONFIG = StoreAnomalyConfig()

_REQUIRED_COLUMNS = {
    "transaction_date",
    "quantity",
    "unit_price",
}


def _prepare_store_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(sales_df, pd.DataFrame):
        raise TypeError("sales_df must be a pandas DataFrame")

    missing = sorted(_REQUIRED_COLUMNS - set(sales_df.columns))
    if missing:
        raise ValueError(f"Missing required sales columns: {missing}")

    clean = remove_exact_duplicates(sales_df).dataframe.copy()

    clean["transaction_date"] = pd.to_datetime(clean["transaction_date"], errors="coerce")
    clean["quantity"] = pd.to_numeric(clean["quantity"], errors="coerce")
    clean["unit_price"] = pd.to_numeric(clean["unit_price"], errors="coerce")

    clean = clean.dropna(
        subset=[
            "transaction_date",
            "quantity",
            "unit_price",
        ]
    )

    clean = clean[(clean["quantity"] > 0) & (clean["unit_price"] > 0)].copy()

    clean["revenue"] = clean["quantity"] * clean["unit_price"]

    return clean.reset_index(drop=True)


def _build_weekly_store_metrics(
    sales_df: pd.DataFrame,
    config: StoreAnomalyConfig,
) -> pd.DataFrame:
    clean = _prepare_store_sales(sales_df)

    if clean.empty:
        return pd.DataFrame(columns=["units_sold", "revenue"])

    clean["period"] = clean["transaction_date"].dt.to_period(config.weekly_frequency)

    return (
        clean.groupby("period")
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("revenue", "sum"),
        )
        .sort_index()
        .astype(float)
    )


def _change_percent(
    current: float,
    baseline: float,
) -> float:
    return ((current - baseline) / baseline) * 100.0


def _historical_baseline(
    weekly_metrics: pd.DataFrame,
    metric: AnomalyMetric,
    config: StoreAnomalyConfig,
) -> float | None:
    """Calculate a baseline from this business's own recent history."""

    if len(weekly_metrics) < config.history_periods + 1:
        return None

    history = weekly_metrics[metric.value].iloc[-(config.history_periods + 1) : -1]

    if len(history) < config.history_periods:
        return None

    baseline = float(history.median())

    if baseline <= 0:
        return None

    return baseline


def calculate_store_historical_baselines(
    sales_df: pd.DataFrame,
    config: StoreAnomalyConfig = (DEFAULT_STORE_ANOMALY_CONFIG),
) -> dict[AnomalyMetric, float]:
    """Return metric baselines from one business's uploaded history."""

    weekly_metrics = _build_weekly_store_metrics(
        sales_df,
        config,
    )

    if weekly_metrics.empty:
        return {}

    baselines: dict[AnomalyMetric, float] = {}

    for metric in (
        AnomalyMetric.UNITS_SOLD,
        AnomalyMetric.REVENUE,
    ):
        baseline = _historical_baseline(
            weekly_metrics,
            metric,
            config,
        )

        if baseline is not None:
            baselines[metric] = baseline

    return baselines


def _is_known_seasonal_pattern(
    weekly_metrics: pd.DataFrame,
    metric: AnomalyMetric,
    current_period: pd.Period,
    current: float,
    config: StoreAnomalyConfig,
) -> bool:
    """Return whether the current value matches a repeated seasonal pattern."""

    current_week = current_period.start_time.isocalendar().week

    seasonal_values = [
        float(
            weekly_metrics.loc[
                period,
                metric.value,
            ]
        )
        for period in weekly_metrics.index
        if (period < current_period and period.start_time.isocalendar().week == current_week)
    ]

    if len(seasonal_values) < config.min_seasonal_history_periods:
        return False

    seasonal_baseline = float(pd.Series(seasonal_values).median())

    if seasonal_baseline == 0:
        return current == 0

    seasonal_deviation = abs(
        _change_percent(
            current,
            seasonal_baseline,
        )
    )

    return seasonal_deviation <= config.seasonal_tolerance_percent


def _detect_metric_change(
    weekly_metrics: pd.DataFrame,
    metric: AnomalyMetric,
    config: StoreAnomalyConfig,
) -> Anomaly | None:
    baseline = _historical_baseline(
        weekly_metrics,
        metric,
        config,
    )

    if baseline is None:
        return None

    current_period = weekly_metrics.index[-1]

    current = float(
        weekly_metrics.loc[
            current_period,
            metric.value,
        ]
    )

    change = _change_percent(
        current,
        baseline,
    )

    if change <= -config.sharp_drop_percent:
        anomaly_type = AnomalyType.SHARP_DROP
        direction = "decreased"
        threshold_text = f"-{config.sharp_drop_percent:g}%"

    elif change >= config.unusual_increase_percent:
        anomaly_type = AnomalyType.UNUSUAL_INCREASE
        direction = "increased"
        threshold_text = f"+{config.unusual_increase_percent:g}%"

    else:
        return None

    if _is_known_seasonal_pattern(
        weekly_metrics,
        metric,
        current_period,
        current,
        config,
    ):
        return None

    period_start = current_period.start_time.date()
    period_end = current_period.end_time.date()

    metric_label = "units sold" if metric is AnomalyMetric.UNITS_SOLD else "revenue"

    return Anomaly(
        anomaly_type=anomaly_type,
        scope=AnomalyScope.STORE,
        metric=metric,
        severity=classify_anomaly_severity(
            anomaly_type,
            change,
        ),
        period_start=period_start,
        period_end=period_end,
        current_value=current,
        baseline_value=baseline,
        change_percent=round(change, 2),
        message=(
            f"Store {metric_label} {direction} by "
            f"{abs(change):.2f}% versus its recent baseline "
            f"(threshold {threshold_text})."
        ),
    )


def detect_store_anomalies(
    sales_df: pd.DataFrame,
    config: StoreAnomalyConfig = (DEFAULT_STORE_ANOMALY_CONFIG),
) -> list[Anomaly]:
    """Detect store-level units-sold and revenue changes."""

    weekly_metrics = _build_weekly_store_metrics(
        sales_df,
        config,
    )

    if weekly_metrics.empty:
        return []

    anomalies = []

    for metric in (
        AnomalyMetric.UNITS_SOLD,
        AnomalyMetric.REVENUE,
    ):
        anomaly = _detect_metric_change(
            weekly_metrics,
            metric,
            config,
        )

        if anomaly is not None:
            anomalies.append(anomaly)

    return anomalies
