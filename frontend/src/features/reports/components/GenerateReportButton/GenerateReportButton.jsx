import { useGenerateReport } from "../../hooks/useGenerateReport";
import "./GenerateReportButton.css";

// Saves the Dashboard's current KPIs/chart series/top products (whatever
// buildDashboardReportData assembled -- see Dashboard.jsx) as a new report,
// then tells the caller so it can refresh ReportDownloadButton, which only
// knows about reports saved before it last checked.
function GenerateReportButton({ data, onGenerated }) {
    const { generate, isGenerating, generateError } = useGenerateReport();

    const handleClick = async () => {
        const report = await generate(data);
        if (report) onGenerated?.(report);
    };

    return (
        <div className="report-generate">
            <button
                type="button"
                className="report-generate-button"
                onClick={handleClick}
                disabled={isGenerating}
            >
                {isGenerating ? "Generating…" : "Generate report"}
            </button>

            {generateError && (
                <p
                    className="report-generate-hint report-generate-hint-error"
                    role="alert"
                >
                    {generateError}
                </p>
            )}
        </div>
    );
}

export default GenerateReportButton;
