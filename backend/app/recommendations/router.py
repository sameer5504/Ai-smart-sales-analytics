"""The recommendations endpoint (US-4.3.x, delivered in chat by US-5.8.2).

Serves a RecommendationsResult for a dataset the user owns. The loading itself
lives in app/recommendations/provider.py, which the chat assistant uses too, so
both give the same answer for the same dataset.

A dataset is addressed by its id and checked against the authenticated user
before anything is read, the same way the dashboard and the assistant do it, so
one user's recommendations can never be built from another user's rows.

Only a dataset that has not been prepared is an error. Having nothing to
recommend comes back 200 with a reason and a message, so the assistant and the
dashboard always have something to render.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.db.datasets_repository import get_dataset_for_user
from app.recommendations.contract import RecommendationsResult
from app.recommendations.provider import (
    NOT_PREPARED_DETAIL,
    RecommendationsProvider,
    get_recommendations_provider,
    load_recommendations,
)

router = APIRouter(
    prefix="/api/recommendations",
    tags=["Recommendations"],
    dependencies=[Depends(get_current_user)],
)

NO_ACCESS_DETAIL = "You do not have access to this dataset."


@router.get("", response_model=RecommendationsResult)
def get_recommendations(
    dataset_id: int = Query(...),
    current_user: dict = Depends(get_current_user),
    provider: RecommendationsProvider = Depends(get_recommendations_provider),
):
    """Return the recommendations for one dataset.

    Args:
        dataset_id: the dataset's id, from GET /api/datasets.

    Returns:
        The RecommendationsResult for that dataset. An unavailable result
        carries a reason and a message rather than an error status.

    Raises:
        HTTPException: 403 when the dataset is not this user's, 404 when its
            rows have not been prepared.
    """
    user_id = current_user["user_id"]

    dataset = get_dataset_for_user(dataset_id, user_id)

    if dataset is None:
        raise HTTPException(
            status_code=403,
            detail=NO_ACCESS_DETAIL,
        )

    # blob_path looks like "datasets/user-13/a1b2c3d4_sales.csv". The stored
    # blob's own name is what load_cleaned expects, not the display filename,
    # since one display filename can have several uploads behind it.
    stored_filename = dataset["blob_path"].rsplit("/", 1)[-1]

    try:
        return load_recommendations(user_id, stored_filename, provider)

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=NOT_PREPARED_DETAIL.format(filename=dataset["filename"]),
        ) from exc
