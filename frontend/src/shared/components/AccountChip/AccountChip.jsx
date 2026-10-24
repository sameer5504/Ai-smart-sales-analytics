import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { authFetch } from "../../utils/authFetch";
import "./AccountChip.css";

const API_URL = import.meta.env.VITE_API_URL;

function AccountChip() {
    const navigate = useNavigate();
    const { isAuthenticated } = useAuth();
    const [displayName, setDisplayName] = useState("");

    useEffect(() => {
        if (!isAuthenticated) {
            return;
        }

        const fetchProfile = async () => {
            try {
                const response = await authFetch(`${API_URL}/auth/profile`, {
                    method: "GET",
                });

                if (!response.ok) {
                    return;
                }

                const data = await response.json();

                setDisplayName(data.display_name || data.username);
            } catch (error) {
                console.error("Failed to load profile:", error);
            }
        };

        const handleProfileUpdate = (event) => {
            setDisplayName(event.detail.display_name || event.detail.username);
        };

        fetchProfile();

        window.addEventListener("profileUpdated", handleProfileUpdate);

        return () => {
            window.removeEventListener("profileUpdated", handleProfileUpdate);
        };
    }, [isAuthenticated]);

    if (!isAuthenticated) {
        return null;
    }

    const initials = (displayName || "U").slice(0, 2).toUpperCase();

    return (
        <div className="account-chip" onClick={() => navigate("/profile")}>
            <span className="account-chip-avatar">{initials}</span>
            {displayName || "Account"}
        </div>
    );
}

export default AccountChip;
