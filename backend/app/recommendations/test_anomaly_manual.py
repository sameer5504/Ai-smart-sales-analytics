from datetime import datetime, timedelta

import pandas as pd

import app.recommendations.service as recommendation_service
from app.recommendations.contract import Evidence
from app.services.product_anomaly_service import detect_product_anomalies


def build_test_data() -> pd.DataFrame:
    rows = []

    start = datetime(2026, 1, 5)

    # Create 10 products with a sharp drop.
    for product_number in range(1, 11):
        product_id = f"P{product_number:03d}"
        product_name = f"Product {product_number}"

        for week in range(5):
            # First 4 weeks: baseline = 10 units
            # Last week: 1 unit -> 90% drop
            quantity = 10 if week < 4 else 1

            rows.append(
                {
                    "transaction_date": start + timedelta(weeks=week),
                    "order_id": f"ORD-P{product_number}-{week}",
                    "product_id": product_id,
                    "product_name": product_name,
                    "quantity": quantity,
                    "unit_price": 20.0,
                }
            )

    return pd.DataFrame(rows)


def fake_build_evidence(anomaly, user_id, filename):
    current = float(anomaly.current_value or 0)
    baseline = float(anomaly.baseline_value or 0)

    units_lost = max(baseline - current, 0)
    revenue_at_risk = units_lost * 20.0

    return Evidence(
        metric=anomaly.metric,
        current_value=current,
        baseline_value=baseline,
        change_percent=anomaly.change_percent,
        units_lost=units_lost,
        revenue_at_risk=revenue_at_risk,
        revenue_share_percent=10.0,
        period_start=anomaly.period_start,
        period_end=anomaly.period_end,
        currency="USD",
    )


# Prevent recommendation evidence from accessing Azure.
recommendation_service.build_evidence = fake_build_evidence


def main() -> None:
    df = build_test_data()

    print("=" * 70)
    print("TEST DATA")
    print("=" * 70)
    print(df)

    print("\n" + "=" * 70)
    print("ANOMALY DETECTION")
    print("=" * 70)

    anomalies = detect_product_anomalies(df)

    print(f"Total anomalies: {len(anomalies)}")

    for index, anomaly in enumerate(anomalies, start=1):
        print(
            f"{index}. "
            f"product={anomaly.product_id} | "
            f"type={anomaly.anomaly_type.value} | "
            f"change={anomaly.change_percent}% | "
            f"severity={anomaly.severity.value}"
        )

    if not anomalies:
        print("No anomalies detected.")
        return

    print("\n" + "=" * 70)
    print("RECOMMENDATION GENERATION")
    print("=" * 70)

    recommendations, suppressed_count = recommendation_service.generate_recommendations(
        anomalies,
        user_id=1,
        filename="manual_test.csv",
        demand_estimates=None,
    )

    print(f"Total findings: {len(anomalies)}")
    print(f"Recommendations returned: {len(recommendations)}")
    print(f"Suppressed recommendations: {suppressed_count}")

    print("\nRecommendations:")

    for index, recommendation in enumerate(recommendations, start=1):
        print(f"{index}. id={recommendation.id} | priority={recommendation.priority} | action={recommendation.action}")


if __name__ == "__main__":
    main()
