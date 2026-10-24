import { Navigate, Outlet } from "react-router-dom";
import { useDatasetContext } from "../../context/DatasetContext";

function RequireDataset() {
    const { datasets, isLoading } = useDatasetContext();

    if (isLoading) {
        return null;
    }

    if (datasets.length === 0) {
        return <Navigate to="/upload" replace />;
    }

    return <Outlet />;
}

export default RequireDataset;
