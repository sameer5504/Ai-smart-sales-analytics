import { Outlet, useLocation } from "react-router-dom";

import AccountChip from "../AccountChip/AccountChip";
import DatasetSelector from "../DatasetSelector/DatasetSelector";
import Sidebar from "../Sidebar/Sidebar";
import "./AppLayout.css";

const PAGE_TITLES = {
    "/": "Dashboard",
    "/dashboard": "Dashboard",
    "/assistant": "Assistant",
    "/upload": "Upload your sales data",
    "/profile": "Profile",
};

function AppLayout() {
    const location = useLocation();
    const pageTitle = PAGE_TITLES[location.pathname] || "";

    return (
        <div className="app-layout">
            <Sidebar />

            <div className="app-layout-main">
                <header className="app-layout-topbar">
                    <span className="app-layout-page-title">{pageTitle}</span>

                    <div className="app-layout-topbar-right">
                        <DatasetSelector />
                        <AccountChip />
                    </div>
                </header>

                <main className="app-layout-content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}

export default AppLayout;
