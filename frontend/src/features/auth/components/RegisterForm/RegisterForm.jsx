import { useNavigate } from "react-router-dom";
import useRegister from "../../hooks/useRegister";
import "./RegisterForm.css";

function RegisterForm() {
    const navigate = useNavigate();

    const { formData, message, isLoading, handleChange, handleSubmit } = useRegister();

    const handleRegister = async (e) => {
        const success = await handleSubmit(e);
        if (success) {
            navigate("/upload");
        }
    };

    return (
        <div className="auth-card">
            <h2 className="auth-card-title">Create your account</h2>
            <p className="auth-card-subtitle">
                You'll upload your first sales file next. Nothing is shared with anyone.
            </p>

            <form className="auth-form" onSubmit={handleRegister}>
                <label>Username</label>
                <input
                    type="text"
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder="Enter your username"
                    required
                />

                <label>Password</label>
                <input
                    type="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Enter your password"
                    required
                />
                <p className="auth-helper-text">At least 10 characters.</p>

                <label>Confirm Password</label>
                <input
                    type="password"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    placeholder="Confirm your password"
                    required
                />

                <button className="auth-btn-primary" type="submit" disabled={isLoading}>
                    {isLoading ? "Creating account..." : "Create account"}
                </button>

                {message && <p className="auth-message">{message}</p>}
            </form>

            <p className="auth-footer-text">
                Already have an account?{" "}
                <span className="auth-link" onClick={() => navigate("/login")}>
                    Sign in
                </span>
            </p>
        </div>
    );
}

export default RegisterForm;
