from app.anomaly.schemas import (
    AnomalySeverity,
    AnomalyType,
)

CRITICAL_DROP_PERCENT = 75.0
WARNING_INCREASE_PERCENT = 200.0


def classify_anomaly_severity(
    anomaly_type: AnomalyType,
    change_percent: float | None,
) -> AnomalySeverity:
    """Return the urgency level for a detected anomaly."""

    if anomaly_type is AnomalyType.DEAD_STOCK:
        return AnomalySeverity.CRITICAL

    if change_percent is None:
        return AnomalySeverity.WARNING

    magnitude = abs(change_percent)

    if anomaly_type is AnomalyType.SHARP_DROP:
        if magnitude >= CRITICAL_DROP_PERCENT:
            return AnomalySeverity.CRITICAL

        return AnomalySeverity.WARNING

    if anomaly_type is AnomalyType.UNUSUAL_INCREASE:
        if magnitude >= WARNING_INCREASE_PERCENT:
            return AnomalySeverity.WARNING

        return AnomalySeverity.INFO

    raise ValueError(f"Unsupported anomaly type: {anomaly_type}")
