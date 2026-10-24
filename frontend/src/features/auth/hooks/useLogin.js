import { useState } from "react";
import { loginUser } from "../services/authService";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../../shared/context/AuthContext";

function useLogin() {
    const [formData, setFormData] = useState({
        username: "",
        password: "",
    });

    const [message, setMessage] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();
    const { setAccessToken } = useAuth();

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });

        setMessage("");
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        setIsLoading(true);
        setMessage("");

        try {
            const data = await loginUser(formData);

            setAccessToken(data.access_token);

            localStorage.setItem("displayName", data.display_name || "");

            localStorage.setItem("username", data.username);

            localStorage.setItem("userId", data.user_id);

            setMessage("Login successful");

            navigate("/", { replace: true });
        } catch {
            setMessage(
                "Login failed. Please check your username and password and try again.",
            );
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

export default useLogin;
