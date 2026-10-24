import KpiCard from "./KpiCard";
import FindingsPanel from "../../recommendations/components/FindingsPanel";
import TopProductsView from "./TopProductsView";
import SalesPerformanceFilters from "../../sales-performance/components/SalesPerformanceFilters/SalesPerformanceFilters";
import SalesPerformanceChart from "../../sales-performance/components/SalesPerformanceChart/SalesPerformanceChart";
import ReportDownloadButton from "../../reports/components/ReportDownloadButton/ReportDownloadButton";
import GenerateReportButton from "../../reports/components/GenerateReportButton/GenerateReportButton";
import ForecastChart from "../../forecast/components/ForecastChart.jsx";
import "../styles/Dashboard.css";

function Dashboard({
    kpis,
    chartSeries,
    topProducts,
    granularity,
    onGranularityChange,
    startDate,
    onStartDateChange,
    endDate,
    onEndDateChange,
    minDate,
    maxDate,
    productOptions,
    selectedProduct,
    onProductChange,
    metric,
    onMetricChange,
    currency,
    datasetId,
    reportData,
    reportsRefreshKey,
    onReportGenerated,
}) {
    return (
        <div className="dashboard-container">
            <div className="dashboard-actions">
                {reportData && (
                    <GenerateReportButton
                        data={reportData}
                        onGenerated={onReportGenerated}
                    />
                )}
                <ReportDownloadButton key={reportsRefreshKey} />
            </div>

            <div className="dashboard-filter-bar">
                <SalesPerformanceFilters
                    granularity={granularity}
                    onGranularityChange={onGranularityChange}
                    startDate={startDate}
                    onStartDateChange={onStartDateChange}
                    endDate={endDate}
                    onEndDateChange={onEndDateChange}
                    minDate={minDate}
                    maxDate={maxDate}
                    productOptions={productOptions}
                    selectedProduct={selectedProduct}
                    onProductChange={onProductChange}
                />
            </div>

            {datasetId && <FindingsPanel datasetId={datasetId} />}

            <div className="kpi-grid">
                {kpis.map((kpi) => (
                    <KpiCard key={kpi.label} kpi={kpi} />
                ))}
            </div>

            <SalesPerformanceChart
                data={chartSeries}
                metric={metric}
                onMetricChange={onMetricChange}
                granularity={granularity}
            />

            <TopProductsView data={topProducts} metric={metric} currency={currency} />

            {/* Next month's revenue forecast for the selected dataset. */}
            {datasetId && <ForecastChart datasetId={datasetId} />}
        </div>
    );
}

export default Dashboard;
