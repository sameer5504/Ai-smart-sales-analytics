# Product-Level Anomaly Detection — MVP Rules

These rules implement US-4.1.3, US-4.1.4, and US-4.1.5.

The user stories do not specify exact numeric thresholds, so the values below are configurable MVP defaults and can be changed after team/mentor review.

## Metric and granularity

- Metric: `units_sold` (`quantity` after sales cleaning).
- Granularity: weekly (`W-SUN`).
- Weekly aggregation reduces day-of-week noise.
- Only store-active weeks are evaluated.
- A whole-store zero-sales week is not counted as product inactivity.

## Sales cleaning

Before detection, the service excludes:

- rows with `quantity <= 0`
- rows with `unit_price <= 0`
- exact duplicate rows

Order ID prefixes are not used to infer cancellations.

## Shared historical baseline

- Baseline window: previous 4 active weeks.
- Baseline statistic: median weekly units sold.
- At least 2 historical weeks must contain positive product sales.
- Change-based alerts require a baseline of at least 5 units.

## US-4.1.3 — Sharp product sales drop

Flag when current weekly units sold are at least 50% below the 4-week median baseline.

Boundary rule:

- Exactly `-50%` is flagged.
- A decrease smaller than 50% is not flagged.

## US-4.1.4 — Product stopped selling / dead stock

Flag when:

1. The product previously had sales in at least 2 active weeks.
2. It records zero units sold for 4 consecutive store-active weeks.

A recently introduced product with insufficient selling history is not marked as dead stock.

## US-4.1.5 — Unusual product sales increase

Flag when current weekly units sold are at least 100% above (2x) the 4-week median baseline.

Boundary rule:

- Exactly `+100%` is flagged.
- An increase below `+100%` is not flagged.

## Unified output

All detections return the shared `Anomaly` schema with:

- anomaly type
- scope
- metric
- severity
- product id/name when product-scoped
- category when available
- evaluated period
- current value
- baseline value
- percent change
- human-readable message