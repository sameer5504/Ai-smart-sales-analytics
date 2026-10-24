import { Outlet, Link } from "react-router-dom";
import "./AuthLayout.css";

function AuthLayout() {
    return (
        <div className="auth-layout">
            <Link to="/" className="auth-layout-logo">
                <span className="auth-layout-logo-mark" />
                <span className="auth-layout-logo-text">Business Analytics</span>
            </Link>

            <Outlet />
        </div>
    );
}

export default AuthLayout;
