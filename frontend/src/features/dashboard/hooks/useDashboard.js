import { useState } from "react";
import { fetchDashboardDetailed } from "../services/dashboardService";
import { cleanRows } from "../utils/aggregateDashboardData";

export function useDashboard() {
    const [rawRows, setRawRows] = useState(null);
    const [isLoadingDashboard, setIsLoadingDashboard] = useState(false);
    const [dashboardError, setDashboardError] = useState("");

    const loadDashboard = async (datasetId) => {
        setIsLoadingDashboard(true);
        setDashboardError("");

        try {
            const detailed = await fetchDashboardDetailed(datasetId);
            const rows = cleanRows(detailed.data);
            setRawRows(rows);
            return rows;
        } catch (error) {
            setDashboardError(error.message);
            return null;
        } finally {
            setIsLoadingDashboard(false);
        }
    };

    const resetDashboard = () => {
        setRawRows(null);
        setDashboardError("");
    };

    return {
        rawRows,
        isLoadingDashboard,
        dashboardError,
        loadDashboard,
        resetDashboard,
    };
}
