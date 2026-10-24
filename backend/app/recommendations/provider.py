"""Getting a RecommendationsResult for one prepared file.

The API route and the chat assistant both need the same answer for the same
file, so loading happens here once rather than in each of them. Every figure in
the result is computed in Python from the user's own rows; nothing downstream
adds to it.

The engine that builds recommendations is not merged yet, so this calls a
provider rather than the engine directly. The default provider reports that
detection could not run. Setting RECOMMENDATIONS_FIXTURES makes it serve the
sample payload from tests/fixtures instead, which is how the chat grounding and
the dashboard entry point are developed before the engine exists. Replacing the
default with the real engine is a one-line change here.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

import pandas as pd

from app.data_pipeline.preparation import load_cleaned
from app.recommendations.contract import (
    REASON_DETECTION_UNAVAILABLE,
    REASON_INSUFFICIENT_HISTORY,
    RecommendationsResult,
)

logger = logging.getLogger(__name__)

# Set this to serve the sample recommendations instead of an unavailable
# result, so the frontend and the assistant can be worked on locally before the
# engine lands. Never set in a deployment.
FIXTURES_ENV_VAR = "RECOMMENDATIONS_FIXTURES"

TRUE_VALUES = {"1", "true", "yes", "on"}

NOT_PREPARED_DETAIL = (
    "No prepared data for '{filename}'. Either it has not been uploaded, or "
    "its required columns could not be identified when it was."
)

NO_ROWS_MESSAGE = "This file has no rows to look at, so there is no history to compare against yet."

ENGINE_UNAVAILABLE_MESSAGE = (
    "Recommendations could not be generated for this file right now. Your data is fine, this is a problem on our side."
)


# A provider takes the prepared rows and returns the finished contract. The
# engine (US-4.3.x) will satisfy this shape.
RecommendationsProvider = Callable[[pd.DataFrame], RecommendationsResult]


def _fixture_provider(df: pd.DataFrame) -> RecommendationsResult:
    """Serve the sample recommendations used to build against the contract.

    Imported inside the function so a deployment, which ships app/ without
    tests/, never reaches for the fixtures.
    """
    from tests.fixtures.recommendations import available_result

    return available_result()


def _unavailable_provider(
    df: pd.DataFrame,
) -> RecommendationsResult:
    return RecommendationsResult.unavailable(
        reason=REASON_DETECTION_UNAVAILABLE,
        message=ENGINE_UNAVAILABLE_MESSAGE,
    )


def get_recommendations_provider() -> RecommendationsProvider:
    """Choose the provider for this request.

    Read per request rather than at import time, so a test can set the
    environment variable and so the deployed default cannot be changed by
    import order.
    """

    if os.getenv(FIXTURES_ENV_VAR, "").lower() in TRUE_VALUES:
        return _fixture_provider

    return _unavailable_provider


def load_recommendations(
    user_id: int,
    stored_filename: str,
    provider: RecommendationsProvider | None = None,
) -> RecommendationsResult:
    """Return the recommendations for one prepared dataset.

    The read only ever touches this user's own folder, so a caller cannot
    reach another user's data even with a stored name that belongs to them.

    Having nothing to recommend is not an error, so an empty file and a failed
    generation both come back as unavailable results with a reason rather than
    as exceptions. Only a dataset that was never prepared raises.

    Args:
        user_id: the authenticated user whose data is being read. Must come
            from the request, never from a value supplied by the client.
        stored_filename: the blob name this upload was stored under, from the
            dataset row, not the display filename. One display filename can
            have several uploads behind it.
        provider: the generator to call. Defaults to the configured one.

    Returns:
        The RecommendationsResult for that dataset.

    Raises:
        FileNotFoundError: if this user has no prepared data under that name.
        ValueError: if the stored name is not a plain filename.
    """
    prepared = load_cleaned(user_id, stored_filename)

    if prepared.empty:
        return RecommendationsResult.unavailable(
            reason=REASON_INSUFFICIENT_HISTORY,
            message=NO_ROWS_MESSAGE,
        )

    try:
        if provider is None:
            provider = get_recommendations_provider()

        return provider(prepared)

    except Exception:
        logger.exception(
            "Could not generate recommendations for %s",
            stored_filename,
        )

        return RecommendationsResult.unavailable(
            reason=REASON_DETECTION_UNAVAILABLE,
            message=ENGINE_UNAVAILABLE_MESSAGE,
        )
