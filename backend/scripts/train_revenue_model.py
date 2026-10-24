"""Retrain the served revenue model and save the artifact.

This is the one-command retrain, for a deployment or for regenerating the artifact
after a change to the model code. It is deliberately thin: it loads the dataset,
scores the model on the expanding backtest as a sanity check, trains on the full
history and writes the file the API loads.

The reasoning behind the model - the data exploration, the benchmarks it was chosen
over, the feature ablation and the hyperparameter search - is in
notebooks/revenue_forecasting_analysis.ipynb, which runs the same training and saves
the same artifact. Read that first if you want to know why the model looks like this.

Usage (from the backend directory):
    PYTHONPATH=. python scripts/train_revenue_model.py path/to/online_retail_II.xlsx
"""

import argparse
import os

import pandas as pd

from app.forecast.daily_series import build_daily_revenue_series
from app.forecast.evaluation import expanding_backtest, mape_by_history
from app.forecast.service import DEFAULT_MODEL_PATH
from app.forecast.trained_revenue_model import TrainedRevenueModel

COUNTRY = "GB"  # the dataset is a UK retailer


def load_daily(path: str) -> pd.Series:
    """Read the dataset and reduce it to a daily revenue series.

    Duplicates are dropped on the full row before the frame is reduced to the revenue
    columns, so identical line items are removed without collapsing distinct ones.
    """
    xl = pd.ExcelFile(path)
    frames = [pd.read_excel(xl, sheet_name=sheet) for sheet in xl.sheet_names]
    raw = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates()
        .rename(columns={"InvoiceDate": "transaction_date", "Quantity": "quantity", "Price": "unit_price"})
    )
    return build_daily_revenue_series(raw).series


def predict_next_month(history: pd.Series) -> float:
    model = TrainedRevenueModel().fit(history, country=COUNTRY)
    return model.forecast_next_month(history, country=COUNTRY).predicted_revenue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", nargs="?", default="notebooks/online_retail_II.xlsx")
    # Defaults to where serving looks when REVENUE_MODEL_PATH is not set, so a freshly
    # trained model is picked up without any further configuration.
    parser.add_argument("--out", default=str(DEFAULT_MODEL_PATH))
    args = parser.parse_args()

    daily = load_daily(args.data)
    print(f"Daily series: {len(daily)} days, {daily.index.min().date()} to {daily.index.max().date()}")

    cold, rich, overall = mape_by_history(expanding_backtest(daily, predict_next_month))
    print(f"MAPE  cold start (<12m): {cold:.1f}%   rich (>=12m): {rich:.1f}%   overall: {overall:.1f}%")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    TrainedRevenueModel().fit(daily, country=COUNTRY).save(args.out)
    print(f"Saved model to {args.out}")


if __name__ == "__main__":
    main()
