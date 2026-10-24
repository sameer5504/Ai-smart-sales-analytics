# Azure AutoML run log

How the AutoML forecasting job was configured, what it returned, and how the endpoint
serving it is managed. The comparison against the model in this repository is in section
6.2 of `backend/notebooks/revenue_forecasting_analysis.ipynb`; this file does not repeat
it.

## The job

`TrainUsingPreprocessedDailyRevenue`, experiment `ForecastingRevenueExploreModels`,
workspace `team-b-ml`.

Trained on `automl_features_revenue.csv`: 739 daily rows from the same preprocessing the
application runs, carrying `date`, `revenue` and ten feature columns. Supplying our own
features rather than a raw file was deliberate — it asks whether AutoML beats the shipped
model *given the same preparation*, which separates the model from the pipeline.

Three of those columns AutoML cannot derive from a date: `is_closed_day`, from the store's
own pattern of zero days; `days_to_holiday` and `days_from_holiday`, which are distances
rather than the holiday flag it does build; and `lag364`.

A second job over the raw transaction file (`automl_transactions_revenue.csv`, 1,067,371
rows) was prepared and set aside. Aggregating transactions drops the days with no rows at
all, and those 135 days are the rest days and holiday shutdowns that carry the strongest
signal, so it would measure a different series rather than a worse model.

### Settings as submitted

| Setting | Value |
| ------- | ----- |
| Task | Time series forecasting |
| Target column | `revenue` |
| Time column | `date` |
| Time series identifiers | none (one business, one series) |
| Forecast horizon | 31 (covers the longest calendar month) |
| Frequency | Day |
| Target aggregate function | none (the asset is already daily) |
| Country for holidays | United Kingdom |
| Primary metric | `r2_score` |
| Cross-validations | 5 |
| Max trials | 1000 |
| Early termination | off |
| Experiment timeout | 25 hours |
| Voting ensemble | on |
| Stack ensemble | off (a meta-learner on this little data overfits) |
| STL decomposition | off (yearly seasonality has two cycles here) |

Allowed models: `LightGBM`, `RandomForest`, `XGBoostRegressor`, `Prophet`,
`SeasonalNaive`, `Naive`. `TCNForecaster` was blocked — deep learning on 739 points spends
the trial budget and loses. About 500 trials completed inside the window.

**`cv_step_size` was left at its default of 1.** That is the single most important thing
on this page: the five cross-validations step forward one day at a time, so they forecast
nearly the same month five times over rather than five separate periods. Section 6.2 works
through what that means for the reported score.

## Result

Best run `trainusingpreprocesseddailyrevenue_491` (`olden_crayon_m0pp5ytp`), a
VotingEnsemble of five XGBoost learners and two random forests, 2m 16s.

| Metric | Value |
| ------ | ----- |
| `r2_score` | 0.8693566 |
| `mean_absolute_error` | 6,018.791 |
| `mean_absolute_percentage_error` | 12.89375 |
| `root_mean_squared_error` | 9,018.470 |
| `normalized_root_mean_squared_error` | 0.06714688 |

The next four runs were XGBoost variants between 0.838 and 0.857, then a RandomForest at
0.831.

## Deployment

| | |
| --- | --- |
| Endpoint | `revenue-forecast-ep` |
| Deployment | `automl-v1` |
| Model | `trainusingprepr491:1` |
| Environment | `MlflowNCDEnv-ai-ml-automl:41` |
| VM | `Standard_DS1_v2`, 1 instance |
| Auth | key |
| Cost | about $0.06/hr, billed whether or not it is called |

The application reads `AZURE_FORECAST_ENDPOINT` and `AZURE_FORECAST_KEY`. With either
missing it serves the local artifact instead, so deleting the endpoint lowers accuracy
rather than breaking the feature.

```
az ml online-endpoint update --name revenue-forecast-ep --traffic "automl-v1=100" \
  --resource-group AI26s-Team-B --workspace-name team-b-ml

az ml online-endpoint delete --name revenue-forecast-ep \
  --resource-group AI26s-Team-B --workspace-name team-b-ml --yes
```

Traffic defaults to 0% on a new deployment, so the first command is required before the
endpoint answers anything.

### Why an endpoint rather than a file

The model cannot be loaded into the application's process. Its `conda_env_v_1_0_0.yml`
pins Python 3.10.19, numpy 1.23.5, pandas 1.5.3 and scikit-learn 1.5.1. The application
runs Python 3.12 with numpy 2.4.6, pandas 2.2.2 and scikit-learn 1.7.2, the last of which
its own LightGBM model requires. pandas 1.5.3 and numpy 1.23.5 have no builds for Python
3.12, so this is a different interpreter rather than a set of versions to downgrade.

## Rebuilding the data assets

From `backend/`:

```
PYTHONPATH=. python scripts/export_automl_dataset.py            # the asset used here
PYTHONPATH=. python scripts/export_automl_dataset.py --minimal  # date and revenue only
PYTHONPATH=. python scripts/export_automl_dataset.py --transactions
```

The transaction export is about 96 MB. All three are gitignored.

Note that the asset used for this run predates `weekday_ratio` being added to
`build_features`, so it carries 12 columns where the script now produces 13. The endpoint
client drops that column to match what the model was trained on.