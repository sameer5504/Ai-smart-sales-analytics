"""Forecast endpoints (US-3.2.1).

``POST /api/forecast`` forecasts from sales records sent in the request body.
``GET /api/forecast/revenue`` forecasts from a file that has already been uploaded
and prepared, which is how the dashboard reaches a business's own data.

Both are compute-only: they return a next-month revenue forecast from the trained
revenue model and do not persist the result. Both require an authenticated user,
since they expose a business's own revenue history.
"""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.data_pipeline.preparation import load_cleaned
from app.db.datasets_repository import get_dataset_for_user
from app.forecast.schemas import ForecastRequest
from app.forecast.service import forecast_from_dataframe

router = APIRouter(
    prefix="/api/forecast",
    tags=["Forecast"],
    dependencies=[Depends(get_current_user)],
)

_COLUMNS = ["transaction_date", "quantity", "unit_price"]


def _run_forecast(
    df: pd.DataFrame,
    *,
    region: str | None,
    country: str | None,
    cannot_forecast: str,
) -> dict:
    """Forecast from ``df`` and return the contract dict.

    A missing column raises ``KeyError``, which means the data lacks a field the
    forecast needs; that is a bad request, not a server error.
    """
    try:
        result = forecast_from_dataframe(df, region=region, country=country)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"{cannot_forecast}: {exc.args[0]}") from exc
    return result.to_dict()


@router.post("")
def create_forecast(request: ForecastRequest) -> dict:
    """Return a next-month total-revenue forecast for the given sales records.

    The response follows the forecast contract:
    ``status`` is "available" or "unavailable", with the predicted total, the
    model used, and the monthly history.
    """
    df = pd.DataFrame([r.model_dump() for r in request.records], columns=_COLUMNS)
    return _run_forecast(
        df,
        region=request.region,
        country=request.country,
        cannot_forecast="The sales records cannot be forecast",
    )


@router.get("/revenue")
def get_revenue_forecast(
    dataset_id: int = Query(..., description="Dataset to forecast from."),
    region: str | None = Query(None, description="Account region for the holiday calendar."),
    country: str | None = Query(None, description="Holiday calendar country code; overrides region."),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Return a next-month total-revenue forecast for one of the user's datasets.

    Reads the rows preparation stored for the dataset instead of parsing the
    upload again, so the forecast is built from the same cleaned data as the rest
    of the application. The response follows the same forecast contract as the
    POST endpoint.

    The dataset is looked up against the authenticated user, and the file is read
    from that user's own storage, so a dataset id belonging to someone else is
    refused rather than answered. Being logged in is not enough to read a file.
    """
    user_id = current_user["user_id"]

    dataset = get_dataset_for_user(dataset_id, user_id)
    if dataset is None:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this dataset.",
        )

    try:
        # The blob's own name, not the display filename: one display filename can
        # have several uploads stored behind it, each under a unique blob name.
        # Same derivation the dashboard route uses.
        stored_filename = dataset["blob_path"].rsplit("/", 1)[-1]
        df = load_cleaned(user_id, stored_filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _run_forecast(
        df,
        region=region,
        country=country,
        cannot_forecast=f"The prepared data for '{dataset['filename']}' cannot be forecast",
    )
