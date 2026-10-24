// Thin fetch wrappers around the backend's /api/mapping/* endpoints.
// Kept in one place so the request/response shape only needs to match the
// backend (see backend/app/data_pipeline/mapping/router.py) in a single spot.

import { authFetch } from "../../../shared/utils/authFetch";

// Same convention as every other service (uploadService, dashboardService,
// authService...): the API's base URL comes from the build's VITE_API_URL and
// nothing else. A hardcoded localhost fallback here used to survive the
// production build, which pins every /api/mapping/* call to the *visitor's*
// own machine when the SPA is served from the backend's origin.
const API_BASE = import.meta.env.VITE_API_URL;

async function parseJsonSafe(response) {
    try {
        return await response.json();
    } catch {
        return null;
    }
}

// Thrown for 422 responses that carry our structured business-validation
// errors (missing required fields, unknown columns, duplicates, etc.), as
// opposed to generic network/server failures.
export class MappingValidationApiError extends Error {
    constructor(errors) {
        super("Mapping validation failed.");
        this.name = "MappingValidationApiError";
        this.errors = errors || {};
    }
}

async function request(path, options) {
    let response;
    try {
        // /api/mapping/* is a protected endpoint (see backend router), so this
        // goes through authFetch (same as uploadService.js) to attach the
        // Authorization header and transparently refresh an expired token.
        response = await authFetch(`${API_BASE}${path}`, options);
    } catch {
        throw new Error("Network error: could not reach the server. Please try again.");
    }
    return response;
}

export async function fetchMappingSchema() {
    const response = await request("/api/mapping/schema");
    if (!response.ok) {
        throw new Error("Failed to load the standard field list from the server.");
    }
    return response.json();
}

export async function suggestMapping(columns) {
    const response = await request("/api/mapping/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ columns }),
    });
    if (!response.ok) {
        throw new Error("Failed to generate mapping suggestions from the server.");
    }
    const data = await response.json();
    return data.suggestions;
}

export async function submitMapping(columns, mapping) {
    const response = await request("/api/mapping/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ columns, mapping }),
    });

    const data = await parseJsonSafe(response);

    if (response.status === 422) {
        const errors = data?.detail?.errors ?? {};
        throw new MappingValidationApiError(errors);
    }

    if (!response.ok) {
        throw new Error(
            data?.detail?.message ||
                data?.message ||
                `Submission failed (${response.status}).`,
        );
    }

    return data;
}

// Finish an upload the automatic matcher couldn't complete on its own: the
// review screen has the user confirm a mapping, and this sends it back
// alongside the file's identity and the currency chosen on the upload page,
// so the backend can re-run the same upload pipeline (/api/upload uses)
// with that mapping instead of guessing again, and register the dataset
// with the currency it actually belongs to.
export async function applyMapping(filename, dataType, currency, columns, mapping) {
    const response = await request("/api/mapping/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            filename,
            data_type: dataType,
            currency,
            columns,
            mapping,
        }),
    });

    const data = await parseJsonSafe(response);

    if (response.status === 422) {
        const errors = data?.detail?.errors ?? {};
        throw new MappingValidationApiError(errors);
    }

    if (!response.ok) {
        const message =
            typeof data?.detail === "string"
                ? data.detail
                : data?.detail?.message ||
                  data?.message ||
                  `Could not finish the upload (${response.status}).`;
        throw new Error(message);
    }

    return data;
}
