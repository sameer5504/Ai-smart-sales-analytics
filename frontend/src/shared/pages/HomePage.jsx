import { useNavigate, Link } from "react-router-dom";
import "./HomePage.css";
import { useAuth } from "../context/AuthContext";
import AccountChip from "../components/AccountChip/AccountChip";

function HomePage() {
    const navigate = useNavigate();
    const { isAuthenticated } = useAuth();

    return (
        <div className="home-page">
            {/* Logo */}
            <header className="home-page-header">
                <Link
                    to={isAuthenticated ? "/dashboard" : "/"}
                    className="home-page-logo"
                >
                    <span className="home-page-logo-mark" />
                    <span className="home-page-logo-text">Business Analytics</span>
                </Link>

                <AccountChip />
            </header>

            <main className="home-page-hero">
                {/* Hero */}
                <h1>Understand your business, in plain language.</h1>

                <p className="home-page-intro">
                    Turn your sales data into clear insights, forecasts, and answers
                    that help you understand your business and make better decisions.
                </p>

                {/* Features */}
                <div className="home-page-features">
                    <div className="home-page-feature-card">
                        <div className="home-page-feature-icon">▦</div>

                        <h2 className="home-page-feature-title">Dashboard</h2>

                        <p className="home-page-feature-text">
                            See your key business metrics and performance in one place.
                        </p>
                    </div>

                    <div className="home-page-feature-card">
                        <div className="home-page-feature-icon">↗</div>

                        <h2 className="home-page-feature-title">Forecasts</h2>

                        <p className="home-page-feature-text">
                            Explore future sales trends and plan ahead with confidence.
                        </p>
                    </div>

                    <div className="home-page-feature-card">
                        <div className="home-page-feature-icon">✦</div>

                        <h2 className="home-page-feature-title">AI Assistant</h2>

                        <p className="home-page-feature-text">
                            Ask questions about your data and get answers in plain
                            language.
                        </p>
                    </div>
                </div>

                {/* Getting Started */}
                <section className="home-page-requirements">
                    <div className="home-page-requirements-icon">✓</div>

                    <div className="home-page-requirements-content">
                        <h2>Ready to get started?</h2>

                        <p>
                            Upload your sales data and let our platform turn it into
                            insights that help you make better decisions and grow your
                            business.
                        </p>

                        <p className="home-page-requirement-note">
                            <strong>Requirement:</strong> A supported sales data file is
                            all you need to get started.
                        </p>
                    </div>
                </section>

                {/* Actions */}
                <div className="home-page-actions">
                    {isAuthenticated ? (
                        <button
                            className="auth-btn-primary"
                            onClick={() => navigate("/upload")}
                        >
                            Start analyzing your data
                        </button>
                    ) : (
                        <>
                            <button
                                className="auth-btn-primary"
                                onClick={() => navigate("/login")}
                            >
                                Sign in
                            </button>

                            <button
                                className="home-page-btn-secondary"
                                onClick={() => navigate("/register")}
                            >
                                Create an account
                            </button>
                        </>
                    )}
                </div>
            </main>
        </div>
    );
}

export default HomePage;
