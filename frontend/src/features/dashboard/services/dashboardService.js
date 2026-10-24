import { authFetch } from "../../../shared/utils/authFetch";
export { fetchDatasets } from "../../../shared/services/datasetsService";

const API_BASE_URL = import.meta.env.VITE_API_URL;

export async function fetchDashboardDetailed(datasetId) {
    const params = new URLSearchParams({ dataset_id: datasetId });
    // /api/dashboard/* requires authentication (see the router's
    // Depends(get_current_user)), so this goes through authFetch to attach
    // the Authorization header and refresh an expired token, the same way
    // uploadService and reportsService do. A bare fetch here returns 401.
    const response = await authFetch(
        `${API_BASE_URL}/api/dashboard/detailed?${params.toString()}`,
    );
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to load dashboard data");
    }

    return data;
}
