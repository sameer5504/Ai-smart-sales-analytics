# Sales Forecasting Model Selection

## Objective

The goal was to select a forecasting model for product-level weekly and monthly sales forecasts using historical sales data.

Model selection was based on time-aware validation rather than random train/test splitting.

## Validation Strategy

Rolling-origin (walk-forward) validation was used to avoid future-data leakage.

### Weekly Forecasting

- Minimum training history: 12 complete weeks
- Validation periods: last 4 complete weeks
- One-step-ahead forecasting
- Validation points: 18,072
- Eligible products: 4,518

### Monthly Forecasting

- Minimum training history: 6 complete months
- Validation periods: last 3 complete months
- One-step-ahead forecasting
- Validation points: 12,732
- Eligible products: 4,244

## Evaluation Metrics

The models were compared using:

- MAE (Mean Absolute Error) as the primary metric
- WAPE (Weighted Absolute Percentage Error)
- Bias to measure systematic over- or under-forecasting

## Statistical Baseline Evaluation

Four baseline models were evaluated:

- Zero forecast
- Naive last-value forecast
- Historical mean
- Moving Average (3)

### Weekly Results

| Model | MAE | WAPE | Bias |
|---|---:|---:|---:|
| Moving Average (3) | 20.6324 | 0.6007 | -1.0781 |
| Naive Last | 23.9226 | 0.6965 | 0.2197 |
| Historical Mean | 26.9725 | 0.7853 | -5.6918 |
| Zero | 34.3456 | 1.0000 | -34.3456 |

Moving Average (3) achieved the lowest overall weekly MAE.

### Monthly Results

| Model | MAE | WAPE | Bias |
|---|---:|---:|---:|
| Moving Average (3) | 60.9139 | 0.5400 | -27.4529 |
| Naive Last | 62.3260 | 0.5525 | -18.2757 |
| Historical Mean | 79.9354 | 0.7086 | -5.4009 |
| Zero | 112.8029 | 1.0000 | -112.8029 |

Moving Average (3) also achieved the lowest overall monthly MAE.

## Machine Learning Challenger

To verify whether a trained machine learning model could provide a meaningful improvement, a global XGBoost regression model was evaluated.

A single global model was trained across products rather than training one model per product, since many products have limited individual history.

### XGBoost Features

The model used historical features including:

- lag_1 through lag_6
- rolling mean over 3 periods
- rolling mean over 6 periods
- rolling minimum and maximum
- recent non-zero sales counts
- recent sales trend
- available history length
- month
- week of year for weekly forecasts

The same walk-forward validation periods used for MA(3) were used for XGBoost.

## MA(3) vs Global XGBoost

### Weekly

| Model | MAE | WAPE | Bias |
|---|---:|---:|---:|
| Moving Average (3) | 20.6324 | 0.6007 | -1.0781 |
| Global XGBoost | 18.8993 | 0.5503 | -9.9172 |

XGBoost reduced overall weekly MAE by approximately 8.40%.

However, it also introduced substantially stronger negative bias.

### Monthly

| Model | MAE | WAPE | Bias |
|---|---:|---:|---:|
| Moving Average (3) | 60.9139 | 0.5400 | -27.4529 |
| Global XGBoost | 60.8326 | 0.5393 | -32.4484 |

XGBoost improved monthly MAE by only approximately 0.13% while also producing worse negative bias.

## Paired Prediction Analysis

Aggregate MAE alone can hide whether a model performs better consistently or only on a smaller number of high-error cases.

Therefore, MA(3) and XGBoost were also compared on identical validation points and at the product level.

### Weekly

- MA(3) produced lower error on 67.37% of validation points.
- XGBoost produced lower error on 32.60% of validation points.
- MA(3) performed better for 63.26% of products.
- XGBoost performed better for 36.74% of products.

Although XGBoost had lower aggregate MAE, the improvement was concentrated in fewer cases with relatively large errors.

### Monthly

- MA(3) produced lower error on 66.30% of validation points.
- XGBoost produced lower error on 33.70% of validation points.
- MA(3) performed better for 68.83% of products.
- XGBoost performed better for 31.17% of products.

The aggregate monthly improvement from XGBoost was negligible.

## Final Decision

Moving Average (3) was retained as the production forecasting model.

The decision was not based only on simplicity. A trained global XGBoost model was evaluated using the same validation strategy and data.

MA(3) was selected because it provides:

- More consistent performance across products and validation points
- Substantially better weekly bias behavior
- Comparable monthly accuracy
- No model-training or model-artifact management requirement
- Lower operational complexity for forecast regeneration

XGBoost remains a possible future optimization if additional historical data or stronger predictive features produce a substantial and consistent improvement.
