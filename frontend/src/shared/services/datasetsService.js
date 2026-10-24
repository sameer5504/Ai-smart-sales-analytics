import { authFetch } from "../utils/authFetch";

const API_BASE_URL = import.meta.env.VITE_API_URL;

// Returns the current user's datasets (backend scopes this to the
// authenticated user - no filename/user info is ever sent from the client).
// Backend responds with { datasets: [...] } (DatasetListResponse), already
// ordered most-recent-first, so this just unwraps it to a plain array.
export async function fetchDatasets() {
    const response = await authFetch(`${API_BASE_URL}/api/datasets`);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to load your files");
    }

    return data.datasets;
}

// Deletes one of the current user's datasets (both the blob in storage and
export async function deleteDataset(datasetId) {
    const response = await authFetch(`${API_BASE_URL}/api/datasets/${datasetId}`, {
        method: "DELETE",
    });

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to delete the file");
    }
}
