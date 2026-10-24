import { logoutUser } from "../../features/auth/services/authService";
import { clearAccessToken } from "../auth/authSession";

export async function logout() {
    const confirmed = window.confirm("Are you sure you want to log out?");

    if (!confirmed) {
        return false;
    }

    try {
        await logoutUser();
    } catch (error) {
        console.error("Logout request failed:", error);
    }

    clearAccessToken();

    localStorage.removeItem("userId");
    localStorage.removeItem("username");
    localStorage.removeItem("displayName");

    return true;
}
