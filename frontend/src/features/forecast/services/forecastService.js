import { authFetch } from "../../../shared/utils/authFetch";

const API_BASE_URL = import.meta.env.VITE_API_URL;

// Requests already in flight, keyed by dataset id. React StrictMode double-invokes
// Effects in development, and a remount can ask for the same forecast again before
// the first answer arrives. Each of those costs a model run on the server, so
// callers arriving while a request is open share its promise instead of opening
// another. The entry is dropped as soon as it settles, so nothing is cached.
const inFlight = new Map();

export function fetchRevenueForecast(datasetId) {
    const open = inFlight.get(datasetId);
    if (open) return open;

    const request = requestRevenueForecast(datasetId).finally(() => {
        inFlight.delete(datasetId);
    });
    inFlight.set(datasetId, request);
    return request;
}

async function requestRevenueForecast(datasetId) {
    const params = new URLSearchParams({ dataset_id: datasetId });
    const response = await authFetch(
        `${API_BASE_URL}/api/forecast/revenue?${params.toString()}`,
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.detail || `Could not load the forecast (${response.status}).`,
        );
    }

    return data;
}
