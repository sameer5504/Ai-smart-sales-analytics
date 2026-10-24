import { useDatasetContext } from "../../context/DatasetContext";
import { NavLink, Link } from "react-router-dom";
import "./Sidebar.css";

function Sidebar() {
    // Same source of truth as the dashboard/chatbot/DatasetSelector - a
    // brand new user (or one who hasn't finished their first upload yet)
    // has an empty datasets list, so there's nothing for Dashboard/
    // Assistant to show yet. While still loading, treat it the same as
    // "no data" rather than flashing the links on then off once the real
    // answer arrives.
    const { datasets, isLoading } = useDatasetContext();
    const hasData = !isLoading && datasets.length > 0;

    return (
        <aside className="sidebar">
            <Link to="/dashboard" className="sidebar-logo">
                <span className="sidebar-logo-mark" />
                <span className="sidebar-logo-text">Business Analytics</span>
            </Link>

            <div className="sidebar-section">
                <p className="sidebar-section-label">Your Business</p>

                {hasData ? (
                    <>
                        <NavLink
                            to="/dashboard"
                            className={({ isActive }) =>
                                `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
                            }
                        >
                            <span className="sidebar-link-icon">☰</span>
                            Dashboard
                        </NavLink>

                        <NavLink
                            to="/assistant"
                            className={({ isActive }) =>
                                `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
                            }
                        >
                            <span className="sidebar-link-icon">✦</span>
                            Assistant
                        </NavLink>

                        <NavLink
                            to="/my-files"
                            className={({ isActive }) =>
                                `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
                            }
                        >
                            <span
                                className="sidebar-link-icon"
                                style={{ color: "#000000" }}
                            >
                                <svg
                                    viewBox="0 0 20 20"
                                    width="16"
                                    height="16"
                                    fill="none"
                                    aria-hidden="true"
                                >
                                    <path
                                        d="M2.5 5.5a1 1 0 0 1 1-1h4l1.5 1.8h7.5a1 1 0 0 1 1 1V15a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1V5.5Z"
                                        stroke="currentColor"
                                        strokeWidth="1.4"
                                        strokeLinejoin="round"
                                    />
                                </svg>
                            </span>
                            My Files
                        </NavLink>
                    </>
                ) : (
                    <p className="sidebar-empty-note">
                        Upload your first file to unlock the dashboard and assistant.
                    </p>
                )}
            </div>

            <div className="sidebar-section">
                <p className="sidebar-section-label">Coming Soon</p>

                <div className="sidebar-link sidebar-link-disabled">
                    <span className="sidebar-link-icon">🕐</span>
                    History
                    <span className="sidebar-badge-soon">Soon</span>
                </div>

                <div className="sidebar-link sidebar-link-disabled">
                    <span className="sidebar-link-icon">⚙</span>
                    Settings
                    <span className="sidebar-badge-soon">Soon</span>
                </div>
            </div>

            <p className="sidebar-footnote">
                History keeps every upload so you can compare months. Settings will hold
                your industry, currency and language.
            </p>
        </aside>
    );
}

export default Sidebar;
