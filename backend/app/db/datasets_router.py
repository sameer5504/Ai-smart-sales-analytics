from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.db.datasets_repository import (
    delete_dataset,
    get_dataset_for_user,
    list_datasets_for_user,
)
from app.db.datasets_schemas import DatasetListResponse
from app.storage.azure_storage import AzureStorage

router = APIRouter(
    prefix="/api/datasets",
    tags=["Datasets"],
    dependencies=[Depends(get_current_user)],
)


def _stored_name(dataset: dict) -> str:
    """Extract the exact blob name a dataset was stored under.

    blob_path looks like "datasets/user-13/a1b2c3d4_sales.csv" - the
    display filename ("sales.csv") is NOT enough to find the blob anymore,
    since re-uploading the same display name creates a separate blob each
    time (see preparation.py's unique stored filename).
    """
    return dataset["blob_path"].rsplit("/", 1)[-1]


@router.get("", response_model=DatasetListResponse)
async def list_my_datasets(current_user: dict = Depends(get_current_user)):
    """List every dataset the authenticated user has uploaded.

    Always scoped to current_user["user_id"] - never accepts a user id
    from the client.

    Self-healing: a dataset row can outlive its blob if the underlying file
    in Azure Blob Storage was ever removed outside the app (e.g. deleted
    directly from the Azure Portal, or a failed cleanup elsewhere). Such a
    row is unusable - the next thing that tries to read it only gets a 404
    - so it's quietly removed here the moment it's noticed rather than
    staying in every listing forever.
    """
    user_id = current_user["user_id"]
    rows = list_datasets_for_user(user_id)

    storage = AzureStorage(user_id=user_id)
    usable_rows = []
    for row in rows:
        if storage.exists(_stored_name(row)):
            usable_rows.append(row)
        else:
            delete_dataset(row["id"], user_id)

    return DatasetListResponse(datasets=usable_rows)


@router.delete("/{dataset_id}")
async def delete_my_dataset(
    dataset_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete one of the authenticated user's datasets.

    Removes both the cleaned file in Azure Blob Storage and the datasets
    table row together, so the two can't drift out of sync the way a
    direct, blob-only deletion (bypassing the app) does.
    """
    user_id = current_user["user_id"]

    dataset = get_dataset_for_user(dataset_id, user_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    storage = AzureStorage(user_id=user_id)
    storage.delete(_stored_name(dataset))

    delete_dataset(dataset_id, user_id)

    return {"deleted": True}
