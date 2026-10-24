import { useNavigate } from "react-router-dom";
import useLogin from "../../hooks/useLogin";
import "./LoginForm.css";

function LoginForm() {
    const navigate = useNavigate();

    const { formData, message, isLoading, handleChange, handleSubmit } = useLogin();

    return (
        <div className="auth-card">
            <h2 className="auth-card-title">Sign in</h2>

            <form className="auth-form" onSubmit={handleSubmit}>
                <label>Username</label>
                <input
                    name="username"
                    value={formData.username}
                    onChange={handleChange}
                    placeholder="Enter username"
                />

                <div className="auth-field-row">
                    <label>Password</label>
                    <span className="auth-link-inline">Forgot password?</span>
                </div>
                <input
                    type="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="Enter password"
                />

                <label className="auth-checkbox-row">
                    <input type="checkbox" />
                    <span>
                        Keep me signed in
                        <small>Leave this off on a shared computer.</small>
                    </span>
                </label>

                <button className="auth-btn-primary" type="submit" disabled={isLoading}>
                    {isLoading ? "Signing in..." : "Sign in"}
                </button>

                {message && <p className="auth-message">{message}</p>}
            </form>

            <p className="auth-footer-text">
                New here?{" "}
                <span className="auth-link" onClick={() => navigate("/register")}>
                    Create an account
                </span>
            </p>
        </div>
    );
}

export default LoginForm;
