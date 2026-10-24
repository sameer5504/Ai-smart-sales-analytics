# Revenue Forecasting — Research & Design Decision

Research outcome for **US-3.2.1 (P1)**: *"As a business owner, I want the system
to forecast my total revenue for the next month."*

The deliverable is a **single next-month total-revenue forecast**. This document
records how it is produced and why.

## What we are forecasting

One number per business: next month's total revenue, computed from that business's
own sales history. Users are SMEs; some upload years of history, many only a few
months.

## Requirement that drives the design

The forecast is served by **one model that is trained once, stored, and reused for
every business** — not a separate model fit per request. It must also **generalize
across stores and regions**: a model trained on one region's data should apply to a
business elsewhere (for example, a different country's holidays and a different rest
day) without retraining. This rules out a per-business model refit on each request
and points to a trained model whose inputs are generic enough to transfer.

## Chosen approach: a trained, transfer-ready model

A gradient-boosting model (LightGBM) is trained once on a daily revenue series and
saved as an artifact the API loads and serves. Three choices make one model work
across businesses of different sizes and different regions:

### Model the ratio to a recent baseline, not raw revenue

The target is revenue divided by the trailing 28-day average, so the model learns
scale-free patterns — a rest day is ~0× the recent average, the day before a holiday
is elevated, a given week of the year runs above or below normal — rather than one
store's absolute numbers. De-normalising is exact (multiply the predicted ratio by
the store's baseline), so a small shop and a large one are the same problem to the
model.

### Read the trading week out of the data, not the calendar

Which weekday a store closes is read from its own history (the weekday that is almost
always zero) instead of assuming a Western weekend. On the test dataset this detects
Saturday; a business that rests on Friday has Friday detected from its data and gets
the same learned "closed day → ~0" effect.

A graded version of the same idea, `weekday_ratio`, gives each weekday's average ratio
to the recent baseline from that store's own history: a rest day lands near 0, a quiet
weekday below 1, the busiest weekday above 1. It is the single most influential feature
in the trained model, and it is region-generic for the same reason the rest-day flag is
— nothing about it assumes which days a business trades.

### Region-generic holiday features

Each date is described by holiday features — is-holiday, holiday eve, day after,
days to and from the nearest holiday — generated from the region's calendar. The
columns are identical for any market; only the dates differ. A holiday effect learned
on one calendar therefore applies when another region's calendar is fed in.

The remaining features are calendar (month, day, week of year) and the same-day value a
year earlier as a ratio to the baseline.

## How the feature set and hyperparameters were chosen

Both were selected on the expanding backtest described under Evaluation, so the choices
favour a model that generalises rather than one that fits a recent window. Both searches
are in the analysis notebook, which re-runs them on every execution and re-checks that
what it selects is still what the code ships.

Four candidate feature groups were defined on top of a base set, and **all sixteen
combinations** were scored: `weekday_ratio`, the days adjacent to a closure, recent
momentum, and smooth seasonal encodings. The scores at the top of that table sit within
a couple of tenths of a percentage point of each other, which is the same order as the
movement caused by changing nothing but LightGBM's random seed, so every candidate is
re-run across ten seeds and the selection rule is fixed in advance:

1. MAPE decides.
2. Sets whose mean MAPE falls within twice the largest seed drift of the best are
   treated as tied, because the measurement cannot separate them.
3. R² breaks the tie — its seed drift is an order of magnitude smaller than its spread.
4. If R² is level too, the smaller feature set wins.

This does not make R² a selection metric. It decides only among candidates MAPE has been
shown unable to tell apart, which is the honest alternative to ranking on noise.

`weekday_ratio` wins. It is the only candidate that improves both regimes — cold start
17.0% → 16.5%, rich history 16.6% → 15.9%. Recent momentum is the strongest feature in
the table on a mature business (rich history 14.0%) and the worst on a new one (cold
start 19.9%); since most users are in their first year, it is left out. The smooth
seasonal encodings are worse than the base set everywhere.

The same rule then selects hyperparameters from a 108-point grid, run with the chosen
feature set. It lands on many shallow trees with a moderate learning rate — 1200
estimators, learning rate 0.05, 3 leaves, minimum 40 samples per leaf. With three leaves
each tree captures close to one effect, so the ensemble stays near-additive; a few
hundred usable days do not support fitting interactions, which is also why supplying the
weekday profile explicitly paid off.

The feature search was run at those hyperparameters and the grid was run at that feature
set, so the two choices agree rather than each assuming the other.

## Why this over a per-business classical model

A per-business model refit on each request (for example Prophet fitted to that
business alone) can be more accurate on a single rich history in principle, but it
cannot satisfy the requirement: nothing is trained once or shared, it re-fits every
request, it has no answer for a brand-new business with little history, and it does not
transfer to another region. The trained model is trained once and served, applies to a
new store on day one by borrowing patterns it has already learned, and carries to other
regions through the generic features above. Across the full backtest it generalises
better than Prophet, which cannot forecast a business's first year at all, so the
shared, deployable model gives up little where it matters.

## Preprocessing

Line items are de-duplicated on the full row, then aggregated into a **daily** revenue
series. A day inside the business's active date range with no transactions is treated
as **zero sales (closed)**, not missing, so rest-day and holiday patterns are learned
rather than interpolated away. Returns are kept and netted into the day, since a
return is real lost revenue.

## Minimum-history rule

**Three complete months.** The expanding backtest scores the model at every history
length, and the result is flat from three months on:

| History available | MAPE |
| ----------------- | ---- |
| 1 month | 100% (the model predicts near zero) |
| 2 months | 32.9% |
| 3 to 5 months | 17.5% |
| 6 to 11 months | 16.0% |
| 12 months or more | 16.1% |

One month clears the 28-day baseline window but leaves almost nothing to train on, so
the model returns a forecast near zero. Two months roughly doubles the steady-state
error. From three months the curve is flat, so that is the floor. Below it, return
**"forecast unavailable"** with a clear reason, matching the KPI-availability pattern.
Never emit a forecast the data can't support.

The last 28 days must also net to a positive total, since the model scales its
prediction against that baseline.

## Evaluation

**Rolling-origin cross-validation** on the test dataset (UCI Online Retail II, one UK
retailer, 24 complete months). Every month from the fourth onward is a fold: the model
is refitted on only the data before that month and asked for that month's total, so no
fold sees its own future. Ordinary k-fold is not valid on a time series, since random
folds would train on months that come after the one being predicted.

Results are split by how much history was available: under a year (cold start, where
most new businesses sit) versus a year or more.

### Metric choice

**MAPE** (mean absolute percentage error, lower is better) selects the model. It is
scale-free, so it means the same thing for a shop taking £200 a day and one taking
£20,000, which is required when one model serves every business and the product states
one accuracy figure for all of them. It is also directly readable by a business owner.
Its weaknesses are that it is undefined at a zero actual (those folds are excluded
rather than allowed to dominate) and that it penalises over-forecasting more than
under-forecasting; neither bites on monthly totals for a trading business.

Four more metrics are reported but not used for selection:

- **MAE** and **RMSE** are in currency, so they cannot be averaged across businesses of
  different sizes or support a single product-wide accuracy claim.
- **R²** measures the share of month-to-month variation the forecast explains, against a
  reference of always predicting the mean of the evaluation period. It is reported
  because it is the standard regression summary, but its reference is a quantity the
  forecaster never had, and it is not scale-free across businesses. It is a good sanity
  check in one direction: a negative R² means the model is worse than a flat line. It is
  also the tie-breaker described above, where MAPE cannot separate two candidates.
- **MASE** divides MAE by the MAE of the naive "next month equals last month" rule, so
  1.0 means no better than doing nothing. It is scale-free and stays defined at zero,
  which makes it the metric to adopt once the model trains across many businesses.

MAPE by regime:

| Model | Cold start (<12 mo) | Rich history (>=12 mo) |
| ----- | ------------------- | ---------------------- |
| **Trained model (chosen)** | **16.5%** | **16.1%** |
| Daily Prophet (benchmark) | 71.1% | 11.3% |
| Moving average (benchmark) | 15.8% | 32.2% |
| Linear trend (benchmark) | 22.3% | 33.3% |

Every metric, over all 21 folds:

| Model | MAPE | MAE | RMSE | R² | MASE |
| ----- | ---- | --- | ---- | -- | ---- |
| **Trained model (chosen)** | **16.3%** | **123,815** | **146,798** | **0.69** | **0.69** |
| Daily Prophet (benchmark) | 36.9% | 278,251 | 405,544 | -1.36 | 1.54 |
| Moving average (benchmark) | 25.2% | 204,353 | 274,720 | -0.08 | 1.13 |
| Linear trend (benchmark) | 28.6% | 228,941 | 296,387 | -0.26 | 1.27 |
| Naive, next month = last month | 22.7% | 180,262 | 239,011 | 0.18 | 1.00 |

The metrics agree, and R² and MASE are harsher on the benchmarks than MAPE is. The
trained model is the only one with a positive R² and the only one below MASE 1.0, so it
is the only model measured here that beats carrying last month forward — with about a
third less absolute error than that rule. Its R² is 0.68 on cold start and 0.70 on rich
history, the same stability the MAPE split shows.

The trained model is the only one that stays steady across both regimes; each benchmark
fails one side. Prophet is the most accurate once a business has a full year (11.3%) but
collapses on cold start (71.1%) because it cannot fit a year of seasonality it has not
seen, and it re-fits per business so it cannot be shared. So the shared model gives up a
little on a mature single business in exchange for working from a business's first months
and transferring across regions. The differences are within the noise of a single-series
test, and the trained model should pull further ahead once it trains on many businesses.

Every figure above is produced by `backend/notebooks/revenue_forecasting_analysis.ipynb`,
which runs the same comparison end to end and then trains and saves the served artifact.
Prophet fits through Stan, whose optimiser lands slightly differently across platforms, so
its exact figure moves by a few points on a re-run; the other three are deterministic.

## Benchmarked against Azure AutoML

An Azure AutoML forecasting job was run on the same preprocessed daily series as an
outside check: daily target, 31-day horizon, five cross-validations, left to search for a
day. Its best model, a voting ensemble of five XGBoost learners and two random forests,
reported **R² 0.869**.

That number is not comparable to the 0.69 above, and the run's own `forecast_table`
artifact shows why. Its five cross-validation folds step forward one day at a time, so
between them they forecast almost the same month five times over: 35 distinct days, all
in the November–December run-up, every fold with close to two years of history behind it,
and no complete calendar month covered at all. The 0.69 above is measured on 21
non-overlapping months, nine of them cold start, on monthly totals rather than daily
values.

Scored on its own task and its own window, however, AutoML is genuinely better than the
shipped model, and that is worth recording rather than explaining away:

| Scored on AutoML's five folds | AutoML | Shipped model |
| ----------------------------- | ------ | ------------- |
| Daily R² | 0.869 | 0.561 |
| Daily MAPE (zero days excluded) | 12.9% | 20.9% |
| Error on the 31-day total | 5.1% | 20.1% |

The shipped model under-forecasts the seasonal run-up on all five windows. Adding back
the momentum feature that the feature search rejected closes about a third of that gap,
to 12.9% — which is the same finding the feature search produced from the other
direction: momentum is the strongest feature on a business with a year or more of history
and the worst on a new one. AutoML's advantage is measured entirely in the mature regime,
which is not the regime most users of this product are in.

Run the other way — AutoML's leading configurations trained on this project's target and
scored on its cross-validation — none of them gets clear of the naive "next month equals
last month" rule. The best reaches 21.8% MAPE and MASE 0.94 against the naive rule's
22.7% and 1.00, and two are worse than doing nothing. The shipped model's 16.3% and 0.69
are a different order of result. The algorithms, then, are not what produced 0.869; the
framing was.

### Serving the AutoML model

AutoML wins the only head-to-head that can be run, so its model is the one the
application serves.

**One model for any business.** The endpoint forecasts pounds at the level it trained on.
The application scales a business's history so its trailing 28-day average matches that
level, asks for a forecast, and divides the answer back — the same normalisation
described above, applied around the model instead of inside it, and exact for a
difference in size. The scaling has to include `lag364`, which the data asset carries as
a raw amount rather than a ratio.

**Called over HTTP, not loaded.** The model was trained under Python 3.10.19 with numpy
1.23.5, pandas 1.5.3 and scikit-learn 1.5.1. This application runs Python 3.12 with numpy
2.4.6, pandas 2.2.2 and scikit-learn 1.7.2, which its own model requires. pandas 1.5.3
and numpy 1.23.5 have no builds for Python 3.12, so the two cannot share a process. The
model is deployed to an Azure managed online endpoint, which gives it its own container.

**What is unmeasured.** The endpoint model trained on all 739 days, so it cannot be
scored on the cross-validation above: every fold is a month it has already seen. Its
accuracy on next-month totals is unknown, and the only numbers behind it are the 35 days
in the table above.

**Fallback.** The trained artifact stays in the repository and is served whenever the
endpoint is unreachable, so a forecast is always available. The response records which
model produced it.

The gap between the two is still a concrete argument for the pooled training described
next, which is what would let a momentum-style signal be estimated across businesses
rather than from one shop's noisy fortnight.

## Training on more data (Other Regions)

The model trains on one UK business, so it is transfer-ready rather than
transfer-proven: the generic features make it react correctly to another region's
rest day and holidays, but the magnitude of, for example, an Eid effect needs real
multi-region data to validate. The clear next step is training across many businesses'
series (with the same scale-free, region-generic features), which both improves
accuracy and validates the cross-region transfer.

## Summary

One gradient-boosting model, trained once and served for every business. Revenue is
modelled as a ratio to the recent baseline (scale-free), the trading week is read from
each store's own data, and holidays come from the region's calendar — so a model trained
on one region applies to others. On an expanding backtest it holds ~16% MAPE whether a
business is in its first year or has years of history, the only model steady across both;
per-business Prophet is kept as the benchmark.
