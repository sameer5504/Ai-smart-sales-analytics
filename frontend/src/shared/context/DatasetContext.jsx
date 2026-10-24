import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react";
import {
    deleteDataset as deleteDatasetRequest,
    fetchDatasets,
} from "../services/datasetsService";

const DatasetContext = createContext(null);

// UX convenience only (remembers the last file the person looked at across
// the dashboard/chatbot) - never the source of truth for what's visible.
const LAST_DATASET_KEY = "lastDatasetId";

export function DatasetProvider({ children }) {
    const [datasets, setDatasets] = useState([]);
    const [datasetId, setDatasetIdState] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState("");

    const applyDatasets = useCallback((list) => {
        setDatasets(list ?? []);

        if (!list || list.length === 0) {
            setDatasetIdState(null);
            return;
        }

        const lastViewedId = sessionStorage.getItem(LAST_DATASET_KEY);
        const stillOwned = list.find((d) => String(d.id) === lastViewedId);
        // list[0] = most recent, since the backend already orders by
        // created_at DESC.
        const chosen = stillOwned ?? list[0];

        setDatasetIdState(chosen.id);
        sessionStorage.setItem(LAST_DATASET_KEY, String(chosen.id));
    }, []);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        setError("");
        try {
            const list = await fetchDatasets();
            applyDatasets(list);
            return list;
        } catch (err) {
            setError(err.message);
            return null;
        } finally {
            setIsLoading(false);
        }
    }, [applyDatasets]);

    useEffect(() => {
        // Fetching the dataset list on mount is exactly what an effect is
        // for (synchronizing with an external system, per React's own
        // docs). refresh() sets isLoading/error synchronously before its
        // first await, which is what this rule flags - there's no
        // render-time equivalent for a real network fetch.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        refresh();
        // Intentionally run once on mount - refresh() is stable (useCallback).
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const selectDataset = useCallback((id) => {
        setDatasetIdState(id);
        sessionStorage.setItem(LAST_DATASET_KEY, String(id));
    }, []);

    // Deletes a dataset and updates local state to match, without a full
    // refetch. If the deleted dataset was the one currently selected, falls
    // back to the next most recent remaining one (or null if none are
    // left) - same "most recent" rule applyDatasets uses on load.
    const deleteDataset = useCallback(
        async (id) => {
            await deleteDatasetRequest(id);

            setDatasets((prev) => {
                const next = prev.filter((d) => d.id !== id);

                if (id === datasetId) {
                    const fallback = next[0] ?? null;
                    setDatasetIdState(fallback ? fallback.id : null);
                    if (fallback) {
                        sessionStorage.setItem(LAST_DATASET_KEY, String(fallback.id));
                    } else {
                        sessionStorage.removeItem(LAST_DATASET_KEY);
                    }
                }

                return next;
            });
        },
        [datasetId],
    );

    const currentDataset = useMemo(
        () => datasets.find((d) => d.id === datasetId) ?? null,
        [datasets, datasetId],
    );

    const value = useMemo(
        () => ({
            datasets,
            datasetId,
            currentDataset,
            selectDataset,
            deleteDataset,
            isLoading,
            error,
            refresh,
        }),
        [
            datasets,
            datasetId,
            currentDataset,
            selectDataset,
            deleteDataset,
            isLoading,
            error,
            refresh,
        ],
    );

    return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

export function useDatasetContext() {
    const ctx = useContext(DatasetContext);
    if (!ctx) {
        throw new Error("useDatasetContext must be used within a <DatasetProvider>");
    }
    return ctx;
}
