import { useEffect, useState } from "react";
import { fetchProfile, updateProfile } from "../services/profileService";

export function useProfile() {
    const [username, setUsername] = useState("");
    const [userId, setUserId] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [message, setMessage] = useState("");

    useEffect(() => {
        const loadProfile = async () => {
            try {
                const data = await fetchProfile();

                setUsername(data.username);
                setUserId(data.user_id);
                setDisplayName(data.display_name || "");
            } catch (error) {
                setMessage(error.message);
            }
        };

        loadProfile();
    }, []);

    const saveProfile = async () => {
        try {
            const data = await updateProfile(displayName);

            setDisplayName(data.display_name);
            setMessage("Profile updated successfully");

            window.dispatchEvent(
                new CustomEvent("profileUpdated", {
                    detail: data,
                }),
            );
        } catch (error) {
            setMessage(error.message);
        }
    };

    const handleDisplayNameChange = (value) => {
        setDisplayName(value);
        setMessage("");
    };

    return {
        username,
        userId,
        displayName,
        message,
        saveProfile,
        handleDisplayNameChange,
    };
}
