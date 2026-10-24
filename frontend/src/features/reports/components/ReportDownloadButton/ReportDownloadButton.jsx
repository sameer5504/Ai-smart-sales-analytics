import { useReportDownload } from "../../hooks/useReportDownload";
import "./ReportDownloadButton.css";

function formatGeneratedAt(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

// Downloads the user's most recent saved report. Reports are listed on
// mount so the button can tell the user whether there is anything to
// download before they click it.
function ReportDownloadButton() {
    const {
        latestReport,
        hasReports,
        isLoadingReports,
        listError,
        isDownloading,
        downloadError,
        downloadLatestReport,
    } = useReportDownload();

    const generatedAt = latestReport
        ? formatGeneratedAt(latestReport.generated_at)
        : null;

    let hint = null;
    if (isLoadingReports) {
        hint = "Checking for saved reports…";
    } else if (listError) {
        hint = listError;
    } else if (!hasReports) {
        hint = "No reports saved yet.";
    } else if (generatedAt) {
        hint = `Latest report generated ${generatedAt}.`;
    }

    return (
        <div className="report-download">
            <button
                type="button"
                className="report-download-button"
                onClick={downloadLatestReport}
                disabled={isLoadingReports || isDownloading || !hasReports}
            >
                <span aria-hidden="true">↓</span>
                {isDownloading ? "Preparing download…" : "Download report"}
            </button>

            {hint && (
                <p
                    className={`report-download-hint${
                        listError || downloadError ? " report-download-hint-error" : ""
                    }`}
                    role={listError || downloadError ? "alert" : undefined}
                >
                    {downloadError || hint}
                </p>
            )}
        </div>
    );
}

export default ReportDownloadButton;
