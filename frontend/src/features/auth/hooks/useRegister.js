import { useState } from "react";
import { registerUser } from "../services/authService";
import { useAuth } from "../../../shared/context/AuthContext";

function useRegister() {
    const [formData, setFormData] = useState({
        username: "",
        password: "",
        confirmPassword: "",
    });

    const [message, setMessage] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const { setAccessToken } = useAuth();

    const handleChange = (e) => {
        setMessage("");

        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const validateForm = () => {
        if (formData.password !== formData.confirmPassword) {
            return "Passwords do not match";
        }

        if (formData.username.length < 3) {
            return "Username must be at least 3 characters";
        }

        if (formData.username.length > 30) {
            return "Username must be less than 30 characters long";
        }

        if (formData.password.length < 6) {
            return "Password must be at least 6 characters";
        }

        if (formData.password.length > 72) {
            return "Password cannot exceed 72 characters";
        }

        return null;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        const validationError = validateForm();

        if (validationError) {
            setMessage(validationError);
            return;
        }

        setIsLoading(true);
        setMessage("");

        try {
            const data = await registerUser({
                username: formData.username,
                password: formData.password,
            });

            setAccessToken(data.access_token);

            localStorage.setItem("userId", data.user_id);

            localStorage.setItem("username", data.username);

            localStorage.setItem("displayName", data.display_name || "");

            return true;
        } catch (error) {
            setMessage(error.message);
            return false;
        } finally {
            setIsLoading(false);
        }
    };

    return {
        formData,
        message,
        isLoading,
        handleChange,
        handleSubmit,
    };
}

export default useRegister;
