import { useEffect, useMemo, useState } from "react";
import { useDashboard } from "../hooks/useDashboard";
import { useDatasetContext } from "../../../shared/context/DatasetContext";
import { useForecast } from "../../forecast/hooks/useForecast.js";
import Dashboard from "../components/Dashboard";
import StateMessage from "../../../shared/components/StateMessage/StateMessage";
import {
    filterByDateRange,
    filterByProduct,
    getProductOptions,
    getDateBounds,
    computeKpiCards,
    computeChartSeries,
    computeTopProductsByMetric,
} from "../utils/aggregateDashboardData";

function DashboardPage() {
    const { rawRows, isLoadingDashboard, dashboardError, loadDashboard } =
        useDashboard();

    // Which dataset is selected lives in DatasetContext, shared with the
    // chatbot - switching it in AppLayout's topbar switches it here too.
    // The selector itself is rendered once, globally, by AppLayout - this
    // page only reads the current selection.
    const {
        datasetId,
        currentDataset,
        isLoading: isLoadingDatasets,
        error: datasetsError,
    } = useDatasetContext();

    const [granularity, setGranularity] = useState("monthly");
    const [metric, setMetric] = useState("total_revenue");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [selectedProduct, setSelectedProduct] = useState("");

    const [lastSeenDatasetId, setLastSeenDatasetId] = useState(datasetId);
    if (datasetId !== lastSeenDatasetId) {
        setLastSeenDatasetId(datasetId);
        setSelectedProduct("");
        setStartDate("");
        setEndDate("");
    }

    // Bumped whenever a report is generated, so ReportDownloadButton (which
    // only checks for saved reports once, on mount) remounts and notices
    // the one just saved instead of staying stuck on "No reports saved yet."
    const [reportsRefreshKey, setReportsRefreshKey] = useState(0);

    // Each dataset carries its own currency now (set at upload time,
    // returned by GET /api/datasets) - no longer read from sessionStorage,
    // which held a single global value that stayed stuck on whichever
    // currency was picked at the *last* upload, regardless of which
    // dataset was actually selected.
    const currency = currentDataset?.currency || null;

    useEffect(() => {
        if (datasetId) {
            loadDashboard(datasetId);
        }
    }, [datasetId]);

    // The same forecast ForecastChart renders for this dataset, requested
    // here too so a generated report can include a snapshot of it.
    // forecastService dedupes concurrent identical requests (see its
    // `inFlight` map), so this doesn't add a second network round trip
    // beyond what ForecastChart already triggers.
    const { data: forecastData, isAvailable: isForecastAvailable } =
        useForecast(datasetId);

    // earliest/latest valid dates in the uploaded file, used to cap the
    // date pickers so the user can't pick a date outside the actual data.
    const dateBounds = useMemo(() => getDateBounds(rawRows || []), [rawRows]);

    // Pre-fill Start/End Date with the dataset's actual range as soon as
    // it's known, so the dashboard opens already showing all of the
    // user's data instead of empty date fields. Waits for dateBounds to
    // actually be ready (non-null) rather than firing the moment the
    // dataset switches - rawRows/dateBounds for a newly selected dataset
    // aren't ready on the same render as the switch itself. Applies once
    // per dataset: if the user clears the dates afterward, this won't
    // silently refill them.
    const [boundsAppliedForDataset, setBoundsAppliedForDataset] = useState(null);
    if (
        datasetId &&
        datasetId !== boundsAppliedForDataset &&
        dateBounds.minDate &&
        dateBounds.maxDate
    ) {
        setBoundsAppliedForDataset(datasetId);
        setStartDate(dateBounds.minDate);
        setEndDate(dateBounds.maxDate);
    }

    // product list for the "Item" filter, built from the full dataset
    // (not the already-filtered rows) so the list doesn't shrink as filters change.
    const productOptions = useMemo(() => getProductOptions(rawRows || []), [rawRows]);

    const filteredRows = useMemo(() => {
        if (!rawRows) return [];
        const byDate = filterByDateRange(rawRows, startDate, endDate);
        return filterByProduct(byDate, selectedProduct);
    }, [rawRows, startDate, endDate, selectedProduct]);

    // pass granularity so Growth Rate cards react to Daily/Weekly/Monthly
    const kpis = useMemo(
        () => computeKpiCards(filteredRows, granularity, currency),
        [filteredRows, granularity, currency],
    );

    const chartSeries = useMemo(
        () => computeChartSeries(filteredRows, granularity),
        [filteredRows, granularity],
    );

    const topProducts = useMemo(
        () => computeTopProductsByMetric(filteredRows, metric, 5),
        [filteredRows, metric],
    );

    // Exactly what "Generate report" saves: the same KPIs/chart/top-products
    // already computed above for display, the forecast chart's data when
    // it's loaded, and the filters that produced them, so a downloaded
    // report says what it's a snapshot of. Only built once there is a
    // dataset to snapshot -- see Dashboard.jsx, which hides the Generate
    // button entirely when this is null.
    const reportData = useMemo(() => {
        if (!datasetId || !currentDataset) return null;
        return {
            dataset_id: datasetId,
            filename: currentDataset.filename,
            currency,
            filters: {
                granularity,
                start_date: startDate || null,
                end_date: endDate || null,
                product: selectedProduct || null,
                metric,
            },
            kpis,
            chart_series: chartSeries,
            top_products: topProducts,
            // null when the forecast hasn't loaded, errored, or has no
            // history to predict from -- the report still saves cleanly
            // without it (see ForecastChart, which shows the same states)
            forecast: isForecastAvailable ? forecastData : null,
        };
    }, [
        datasetId,
        currentDataset,
        currency,
        granularity,
        startDate,
        endDate,
        selectedProduct,
        metric,
        kpis,
        chartSeries,
        topProducts,
        isForecastAvailable,
        forecastData,
    ]);

    const handleReportGenerated = () => setReportsRefreshKey((key) => key + 1);

    if (isLoadingDatasets) {
        return (
            <StateMessage
                variant="loading"
                title="Loading your dashboard"
                message="This only takes a moment."
            />
        );
    }

    if (datasetsError) {
        return (
            <StateMessage
                variant="critical"
                icon="!"
                title="Couldn't load your data"
                message={datasetsError}
                actionLabel="Try again"
                onAction={() => window.location.reload()}
            />
        );
    }

    // Genuinely no dataset selected (e.g. this user has never uploaded
    // anything) - the only real "empty state" left. A missing *currency*
    // used to trigger this same branch and silently drop productOptions/
    // date-range props - that's fixed now; formatCurrency handles a missing
    // currency gracefully on its own, so a known dataset with an unknown
    // currency still gets the full dashboard, filters included.
    if (!datasetId) {
        return (
            <Dashboard
                kpis={kpis}
                chartSeries={chartSeries}
                topProducts={topProducts}
                granularity={granularity}
                onGranularityChange={setGranularity}
                startDate={startDate}
                onStartDateChange={setStartDate}
                endDate={endDate}
                onEndDateChange={setEndDate}
                metric={metric}
                onMetricChange={setMetric}
                reportsRefreshKey={reportsRefreshKey}
            />
        );
    }

    if (isLoadingDashboard) {
        return (
            <StateMessage
                variant="loading"
                title="Loading your dashboard"
                message="This only takes a moment."
            />
        );
    }

    if (dashboardError) {
        return (
            <StateMessage
                variant="critical"
                icon="!"
                title="Couldn't load dashboard data"
                message={dashboardError}
                actionLabel="Try again"
                onAction={() => loadDashboard(datasetId)}
            />
        );
    }

    return (
        <Dashboard
            kpis={kpis}
            chartSeries={chartSeries}
            topProducts={topProducts}
            granularity={granularity}
            onGranularityChange={setGranularity}
            startDate={startDate}
            onStartDateChange={setStartDate}
            endDate={endDate}
            onEndDateChange={setEndDate}
            minDate={dateBounds.minDate}
            maxDate={dateBounds.maxDate}
            productOptions={productOptions}
            selectedProduct={selectedProduct}
            onProductChange={setSelectedProduct}
            metric={metric}
            onMetricChange={setMetric}
            currency={currency}
            datasetId={datasetId}
            reportData={reportData}
            reportsRefreshKey={reportsRefreshKey}
            onReportGenerated={handleReportGenerated}
        />
    );
}

export default DashboardPage;
