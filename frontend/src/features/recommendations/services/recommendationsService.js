import { authFetch } from "../../../shared/utils/authFetch";

const API_BASE_URL = import.meta.env.VITE_API_URL;

/**
 * Fetch the recommendations for a dataset the user owns.
 *
 * Having nothing to recommend is not an error: that comes back as a normal
 * response with status "unavailable" and a message worth showing. A dataset
 * belonging to someone else is a 403, and one that was never prepared a 404.
 */
export async function fetchRecommendations(datasetId) {
    const params = new URLSearchParams({ dataset_id: datasetId });

    const response = await authFetch(
        `${API_BASE_URL}/api/recommendations?${params.toString()}`,
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to load recommendations");
    }

    return data;
}
