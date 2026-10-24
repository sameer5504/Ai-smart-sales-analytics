from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.dashboard.schemas import DashboardDetailedResponse, DataQuality
from app.data_pipeline.preparation import load_cleaned
from app.db.datasets_repository import get_dataset_for_user

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/detailed", response_model=DashboardDetailedResponse)
async def get_dashboard_detailed(
    dataset_id: int = Query(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]

    dataset = get_dataset_for_user(dataset_id, user_id)
    if dataset is None:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this dataset.",
        )

    try:
        # blob_path looks like "datasets/user-13/a1b2c3d4_sales.csv" - we
        # need just the stored blob's own name, not the display filename,
        # since one display filename can now have several uploads stored
        # behind it.
        stored_filename = dataset["blob_path"].rsplit("/", 1)[-1]
        df = load_cleaned(user_id, stored_filename)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No data has been uploaded yet.",
        ) from exc

    df = df.copy()

    # order_id and product_id are mandatory on every displayed row (see
    # DashboardRow in schemas.py) - a row missing either is dropped here,
    # same as a row missing a core numeric/date field. category is the only
    # genuinely optional column and is left nullable below.
    df = df.dropna(subset=["quantity", "unit_price", "transaction_date", "order_id", "product_id"])

    df["date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")

    if "category" not in df.columns:
        df["category"] = None

    df = df.astype(object).where(df.notna(), None)

    records = df.to_dict(orient="records")

    return DashboardDetailedResponse(
        data=records,
        data_quality=DataQuality(total_rows=len(df)),
    )
