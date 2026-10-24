"""Build the data assets for the Azure AutoML benchmark described in docs/automl_benchmark.md.

Two jobs are compared against the model in notebooks/revenue_forecasting_analysis.ipynb,
and this script produces the input for each:

  --transactions  the source file unchanged, only reshaped into something a forecasting
              service accepts: both sheets concatenated into one CSV, every original
              column kept, and a `revenue` column added because a target is required and
              the source has quantity and price rather than revenue. Nothing is
              deduplicated, nothing is aggregated, no day is filled in. The service is
              expected to roll this up itself with a daily frequency and a sum
              aggregation. See the warning below before relying on the result.

  --minimal   date and revenue only, already aggregated to a day by this pipeline. The
              fallback if the transaction-level asset will not train, and the cleaner
              comparison in any case.

  (default)   the same series plus the calendar features the shipped model uses. Three of
              them are the reason to send more than two columns, because AutoML cannot
              derive them: is_closed_day, which comes from the store's own pattern of zero
              days rather than from a calendar; days_to_holiday and days_from_holiday,
              which are distances rather than the holiday flag AutoML does build; and
              lag364. The rest (month, day, weekofyear, and the three holiday binaries)
              are included for completeness and AutoML would generate equivalents itself.

Both write the daily series exactly as the application builds it: deduplicated on the
full row, aggregated to one revenue total per calendar day, and reindexed onto a complete
date range so a non-trading day is a zero rather than a gap. That last step matters more
than it looks. 135 of the 739 days have no sales, and a service that aggregated raw
transactions itself would see them as missing and impute them, which would erase the
rest-day and holiday pattern the forecast depends on.

Identifiers are dropped from the aggregated exports. Invoice, StockCode, Description,
Customer ID and Country are needed while cleaning and meaningless once the rows are
aggregated to a day, and quantity and unit price are the factors of the target rather
than predictors of it. The --transactions export keeps them, since its whole purpose is
to be the source data unchanged.

Warning about --transactions. Three things this pipeline does are left undone, and each
changes the series the service would train on:

  135 of the 739 days have no sales at all, and a day with no sales has no rows. Once
  aggregated they arrive as gaps rather than zeros, so the service imputes them. Those
  are the rest days and holiday shutdowns, and they average 93 against 31,055 for an
  ordinary trading day. Imputing them removes the strongest signal the forecast has.

  34,335 exact duplicate rows are kept, which inflates revenue.

  212 accounting rows carrying -369,000 are kept, which lands as artificial cliffs.

Two column sets were measured and rejected, recorded here so they are not retried:

  Daily counts from the transaction rows (invoices, customers, products, units, average
  basket, returns), lagged so they would be known at forecast time. Every one made the
  forecast worse on the rolling-origin backtest, moving MAPE from 16.7% to between 21.6%
  and 25.4%. Lagged far enough to be usable they are a stale copy of revenue itself.

  Dropping the accounting stock codes (AMAZONFEE, B, BANK CHARGES, ADJUST, ADJUST2) does
  improve the forecast, to 13.7% MAPE, since 212 rows carrying -369,000 land as artificial
  cliffs. It is not done here because it also changes the target, so a model trained on a
  filtered series cannot be compared with one that was not.

Usage (from the backend directory):
    PYTHONPATH=. python scripts/export_automl_dataset.py --transactions
    PYTHONPATH=. python scripts/export_automl_dataset.py --minimal
    PYTHONPATH=. python scripts/export_automl_dataset.py
    PYTHONPATH=. python scripts/export_automl_dataset.py --train-until 2011-05-31
"""

import argparse
from pathlib import Path

import pandas as pd

from app.forecast.daily_series import build_daily_revenue_series
from app.forecast.trained_revenue_model import BASELINE_WINDOW, build_features, detect_closed_days

DEFAULT_DATA = "notebooks/online_retail_II.xlsx"
FEATURES_OUT = "notebooks/automl_features_revenue.csv"
MINIMAL_OUT = "notebooks/automl_minimal_revenue.csv"
TRANSACTIONS_OUT = "notebooks/automl_transactions_revenue.csv"
YEAR_LAG = 364  # same weekday one year back, as in the model's own features
COUNTRY = "GB"  # the dataset is a UK retailer


def load_daily_series(path: str) -> pd.Series:
    """Read every sheet and reduce it to one revenue total per calendar day.

    Deduplication happens on the whole row, before any column is dropped. Reducing to the
    revenue columns first would collapse two different products sold at the same price on
    the same day into one row, and costs 442,202 genuine line items on this dataset.
    """
    xl = pd.ExcelFile(path)
    frames = [pd.read_excel(xl, sheet_name=sheet) for sheet in xl.sheet_names]
    rows = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates()
        .rename(columns={"InvoiceDate": "transaction_date", "Quantity": "quantity", "Price": "unit_price"})
    )
    return build_daily_revenue_series(rows).series


def calendar_features(series: pd.Series) -> pd.DataFrame:
    """The model's calendar features, from app.forecast.build_features.

    ``lag364_ratio`` is replaced by the raw value a year back: the ratio is expressed
    against the model's own baseline and only means something inside its normalisation.
    Rest days are detected once over the whole series so the flag does not drift, which is
    a small lookahead against a service's own validation folds and is noted in the docs.
    """
    closed_days = detect_closed_days(series)
    baseline = series.shift(1).rolling(BASELINE_WINDOW).mean().to_numpy()
    frame = build_features(series.index, series, baseline, COUNTRY, closed_days)
    frame = frame.drop(columns=["lag364_ratio"])
    frame[f"lag{YEAR_LAG}"] = series.shift(YEAR_LAG).to_numpy()
    return frame.reset_index(drop=True)


def load_transactions(path: str) -> pd.DataFrame:
    """Both sheets concatenated, every column kept, with a revenue column added."""
    xl = pd.ExcelFile(path)
    frames = [pd.read_excel(xl, sheet_name=sheet) for sheet in xl.sheet_names]
    rows = pd.concat(frames, ignore_index=True)
    rows["revenue"] = (rows["Quantity"] * rows["Price"]).round(2)
    return rows


def build_frame(series: pd.Series, *, minimal: bool) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "date": series.index.strftime("%Y-%m-%d"),
            "revenue": series.to_numpy().round(2),
        }
    )
    if minimal:
        return frame
    return pd.concat([frame, calendar_features(series)], axis=1)


def write(frame: pd.DataFrame, path: str) -> None:
    frame.to_csv(path, index=False)
    revenue = frame["revenue"]
    dates = pd.to_datetime(frame["date"])
    gaps = len(pd.date_range(dates.iloc[0], dates.iloc[-1], freq="D")) - len(frame)
    print(f"Wrote {path}: {len(frame)} rows, {frame['date'].iloc[0]} to {frame['date'].iloc[-1]}")
    print(f"  zero-revenue days {int((revenue == 0).sum())}, calendar gaps {gaps}, {len(frame.columns)} columns")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", nargs="?", default=DEFAULT_DATA)
    parser.add_argument(
        "--transactions", action="store_true", help="the source file unchanged, one CSV, for the service to aggregate"
    )
    parser.add_argument(
        "--minimal", action="store_true", help="date and revenue only, letting the service derive everything"
    )
    parser.add_argument("--out", help="output path (defaults by mode)")
    parser.add_argument("--train-until", help="also split into train and test files at this date, e.g. 2011-05-31")
    args = parser.parse_args()

    if args.transactions:
        rows = load_transactions(args.data)
        out = args.out or TRANSACTIONS_OUT
        rows.to_csv(out, index=False)
        days = pd.to_datetime(rows["InvoiceDate"], errors="coerce").dt.normalize()
        print(f"Wrote {out}: {len(rows):,} rows, {len(rows.columns)} columns")
        print(
            f"  distinct days with sales {days.nunique()} of "
            f"{(days.max() - days.min()).days + 1} calendar days in range"
        )
        print(f"  duplicate rows kept {int(rows.duplicated().sum()):,}")
        return

    series = load_daily_series(args.data)
    frame = build_frame(series, minimal=args.minimal)
    out = args.out or (MINIMAL_OUT if args.minimal else FEATURES_OUT)
    write(frame, out)

    if not args.train_until:
        return

    cutoff = pd.Timestamp(args.train_until)
    is_train = pd.to_datetime(frame["date"]) <= cutoff
    path = Path(out)
    for part, subset in (("train", frame[is_train]), ("test", frame[~is_train])):
        write(subset.reset_index(drop=True), str(path.with_name(f"{path.stem}_{part}{path.suffix}")))


if __name__ == "__main__":
    main()
