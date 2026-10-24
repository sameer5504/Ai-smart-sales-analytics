import pandas as pd

from app.anomaly.schemas import Anomaly
from app.services.product_anomaly_service import (
    detect_product_anomalies,
)
from app.services.store_anomaly_service import (
    detect_store_anomalies,
)


def detect_anomalies(
    sales_df: pd.DataFrame,
) -> list[Anomaly]:
    """Return all detected anomalies using the shared Anomaly schema."""

    store_anomalies = detect_store_anomalies(sales_df)
    product_anomalies = detect_product_anomalies(sales_df)

    return [
        *store_anomalies,
        *product_anomalies,
    ]
