import { refreshAccessToken } from "../../features/auth/services/authService";
import { clearAccessToken, getAccessToken, setAccessToken } from "../auth/authSession";

let refreshPromise = null;

async function refreshSession() {
    if (!refreshPromise) {
        refreshPromise = refreshAccessToken()
            .then((data) => {
                setAccessToken(data.access_token);
                return data.access_token;
            })
            .catch((error) => {
                clearAccessToken();
                throw error;
            })
            .finally(() => {
                refreshPromise = null;
            });
    }

    return refreshPromise;
}

export async function authFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});

    const accessToken = getAccessToken();

    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }

    let response = await fetch(url, {
        ...options,
        headers,
        credentials: "include",
    });

    if (response.status !== 401) {
        return response;
    }

    try {
        const newAccessToken = await refreshSession();

        headers.set("Authorization", `Bearer ${newAccessToken}`);

        response = await fetch(url, {
            ...options,
            headers,
            credentials: "include",
        });

        if (response.status === 401) {
            clearAccessToken();
        }

        return response;
    } catch {
        return response;
    }
}
