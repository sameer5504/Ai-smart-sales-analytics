import { useEffect, useMemo, useState } from "react";
import { fetchRevenueForecast } from "../services/forecastService.js";
import { buildChartGeometry } from "../../../shared/utils/forecastChartGeometry.js";

// Guards against a malformed/incomplete response so the chart can show a
// clear "invalid data" state instead of crashing on `.map` of `undefined`
// or rendering NaN coordinates.
function isValidForecastResponse(data) {
    if (!data || typeof data !== "object") return false;
    if (data.status !== "available" && data.status !== "unavailable") return false;
    if (!Array.isArray(data.history)) return false;
    return data.history.every(
        (p) =>
            p &&
            typeof p.month === "string" &&
            typeof p.revenue === "number" &&
            Number.isFinite(p.revenue),
    );
}

// Fetches the revenue forecast for one of the user's datasets and derives
// the chart's SVG geometry from it. The dataset id comes from DatasetContext,
// the same selection the dashboard and chatbot read, and the backend resolves
// it to a file it has checked the caller owns.
export function useForecast(datasetId) {
    const [loadedDatasetId, setLoadedDatasetId] = useState(datasetId);
    const [state, setState] = useState({ status: "loading" });
    const [activeKey, setActiveKey] = useState(null);

    // `datasetId` changing means a different dataset is being viewed. Reset to
    // the loading state and clear any hovered/focused point right away, during
    // this render, instead of via an Effect — that way the stale forecast for
    // the previous dataset is never shown, not even for a frame, and the Effect
    // below is left to do only what an Effect should: synchronize with the
    // fetch.
    if (datasetId !== loadedDatasetId) {
        setLoadedDatasetId(datasetId);
        setState({ status: "loading" });
        setActiveKey(null);
    }

    useEffect(() => {
        if (!datasetId) return undefined;

        let cancelled = false;

        fetchRevenueForecast(datasetId)
            .then((data) => {
                if (cancelled) return;
                if (!isValidForecastResponse(data)) {
                    setState({ status: "invalid" });
                    return;
                }
                setState({ status: "loaded", data });
            })
            .catch((err) => {
                if (!cancelled)
                    setState({ status: "error", errorMessage: err.message });
            });

        return () => {
            cancelled = true;
        };
    }, [datasetId]);

    const data = state.status === "loaded" ? state.data : null;
    const isAvailable = data?.status === "available";

    const forecastInput = useMemo(() => {
        if (!isAvailable) return null;
        return {
            targetMonth: data.target_month,
            predictedRevenue: data.predicted_revenue,
            interval: data.interval,
        };
    }, [isAvailable, data]);

    const geometry = useMemo(() => {
        if (!data) return null;
        return buildChartGeometry(data.history, forecastInput);
    }, [data, forecastInput]);

    const hasHistory = Boolean(data && data.history.length > 0);

    const allPoints = useMemo(() => {
        if (!geometry) return [];
        return geometry.forecastPoint
            ? [...geometry.historyPoints, geometry.forecastPoint]
            : geometry.historyPoints;
    }, [geometry]);

    const activePoint = allPoints.find((p) => p.month === activeKey) || null;

    return {
        status: state.status,
        errorMessage: state.errorMessage,
        data,
        isAvailable,
        geometry,
        hasHistory,
        activeKey,
        activePoint,
        setActiveKey,
    };
}
