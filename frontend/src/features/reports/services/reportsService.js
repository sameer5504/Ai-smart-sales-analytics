// Thin fetch wrappers around the backend's /api/reports/* endpoints.
// Kept in one place so the request/response shape only needs to match the
// backend (see backend/app/reports/router.py) in a single spot.

import { authFetch } from "../../../shared/utils/authFetch";

const API_BASE_URL = import.meta.env.VITE_API_URL;

async function request(path, options) {
    let response;
    try {
        // /api/reports/* is a protected endpoint (see backend router), so
        // this goes through authFetch to attach the Authorization header
        // and transparently refresh an expired token.
        response = await authFetch(`${API_BASE_URL}${path}`, options);
    } catch {
        throw new Error("Network error: could not reach the server. Please try again.");
    }
    return response;
}

async function parseJsonSafe(response) {
    try {
        return await response.json();
    } catch {
        return null;
    }
}

export async function fetchReports() {
    const response = await request("/api/reports");

    if (!response.ok) {
        throw new Error("Failed to load your reports from the server.");
    }

    const data = await response.json();
    return data.reports;
}

export async function fetchReport(reportId) {
    const response = await request(
        `/api/reports/download/${encodeURIComponent(reportId)}`,
    );

    const data = await parseJsonSafe(response);

    if (response.status === 404) {
        throw new Error("That report is no longer available.");
    }

    if (!response.ok) {
        throw new Error(
            typeof data?.detail === "string"
                ? data.detail
                : `Could not download the report (${response.status}).`,
        );
    }

    return data;
}

// Saves the caller's data as a new report. The Dashboard page is the
// current caller -- see useGenerateReport -- sending its current
// KPIs/chart series/top products exactly as computed for display, since
// the backend has no server-side equivalent of that computation to redo
// it from (see backend/app/reports/service.py's save_report docstring).
export async function generateReport(data) {
    const response = await request("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data }),
    });

    const body = await parseJsonSafe(response);

    if (!response.ok) {
        throw new Error(
            typeof body?.detail === "string"
                ? body.detail
                : `Could not generate the report (${response.status}).`,
        );
    }

    return body;
}
