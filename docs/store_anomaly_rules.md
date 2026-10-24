# Store-Level Anomaly Detection — MVP Rules

These rules implement US-4.1.1, US-4.1.2, and US-4.1.6.

The user stories do not define exact numeric thresholds, so the values below are configurable MVP defaults and can be adjusted after team or mentor review.

## Metrics and granularity

Store-level anomaly detection evaluates two metrics independently:

- `units_sold`
- `revenue`

Granularity:

- Weekly (`W-SUN`)

Units sold and revenue are evaluated separately because they can move in different directions.

## Historical baseline

Each business is evaluated against its own uploaded sales history rather than against a global baseline.

For each metric:

- Baseline window: previous 4 weekly periods.
- Baseline statistic: median.
- The current period is excluded from the baseline.
- At least 4 historical periods are required.
- A non-positive baseline is not used for percentage-based anomaly detection.

## Sharp drop detection

A sharp drop is detected when the current value is at least 50% below the historical baseline.

Boundary rule:

- Exactly `-50%` is flagged.
- A decrease smaller than 50% is not flagged.

The rule is applied independently to:

- units sold
- revenue

## Unusual increase detection

An unusual increase is detected when the current value is at least 100% above the historical baseline.

Boundary rule:

- Exactly `+100%` is flagged.
- An increase below `+100%` is not flagged.

The rule is applied independently to:

- units sold
- revenue

## Seasonal false-positive filtering

Before returning a detected store-level anomaly, the service checks whether the current value matches a known repeating seasonal pattern.

MVP seasonal rules:

- Compare the current ISO week with the same ISO week from previous years.
- At least 2 previous matching seasonal periods are required.
- The seasonal baseline is the median of those historical values.
- If the current value is within 20% of the seasonal baseline, the finding is treated as an expected seasonal pattern and is not returned as an anomaly.
- If there is insufficient seasonal history, normal anomaly detection is used.

## Severity classification

Severity classification is centralized and shared by store-level and product-level anomaly detection.

Current MVP rules:

- Dead stock: `critical`
- Sharp drop of 75% or more: `critical`
- Sharp drop below 75%: `warning`
- Unusual increase below 200%: `info`
- Unusual increase of 200% or more: `warning`

## Automatic detection after upload

Anomaly detection runs automatically after a successfully prepared sales upload.

Detection runs only when:

- the upload is a sales dataset
- preparation and validation succeeded
- the prepared dataset was stored successfully

Incomplete uploads do not trigger anomaly detection.

## Unified output

Store-level and product-level detection are exposed through one detection entry point.

The unified detector returns:

`list[Anomaly]`

Every result uses the shared `Anomaly` schema.

The schema distinguishes findings through:

- `anomaly_type` — what kind of change occurred
- `scope` — store or product
- `metric` — units sold or revenue
- `severity` — critical, warning, or info

Store-level detection does not introduce separate store-specific anomaly types.