import { authFetch } from "../../../shared/utils/authFetch";

const API_URL = import.meta.env.VITE_API_URL;

export async function fetchProfile() {
    const response = await authFetch(`${API_URL}/auth/profile`, {
        method: "GET",
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to load profile");
    }

    return data;
}

export async function updateProfile(displayName) {
    const response = await authFetch(`${API_URL}/auth/profile`, {
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            display_name: displayName,
        }),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to update profile");
    }

    return data;
}
