import { useEffect, useState } from "react";
import { fetchReport, fetchReports } from "../services/reportsService";

// Turns a report's JSON into a file the browser saves, since
// /api/reports/download/{id} returns the report as JSON rather than as a
// file stream (see backend/app/reports/router.py).
function saveAsJsonFile(report) {
    const url = URL.createObjectURL(
        new Blob([JSON.stringify(report, null, 2)], {
            type: "application/json",
        }),
    );

    const link = document.createElement("a");
    link.href = url;
    link.download = `report-${report.report_id}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
}

// Business logic for downloading a saved report, kept separate from the
// button's presentation per the project's Page -> Hook -> Service -> API
// layering (see useDashboard.js).
//
// The list is loaded on mount so the button can say whether there is
// anything to download; a report's full payload is only fetched when the
// user actually asks for it.
export function useReportDownload() {
    const [reports, setReports] = useState(null);
    const [listError, setListError] = useState("");
    const [isDownloading, setIsDownloading] = useState(false);
    const [downloadError, setDownloadError] = useState("");

    useEffect(() => {
        let cancelled = false;

        fetchReports()
            .then((list) => {
                if (!cancelled) setReports(list);
            })
            .catch((error) => {
                if (cancelled) return;
                setListError(error.message);
                setReports([]);
            });

        return () => {
            cancelled = true;
        };
    }, []);

    const downloadReport = async (reportId) => {
        // Guard against duplicate downloads (double-click, slow network).
        if (isDownloading) return;

        setIsDownloading(true);
        setDownloadError("");

        try {
            saveAsJsonFile(await fetchReport(reportId));
        } catch (error) {
            setDownloadError(error.message);
        } finally {
            setIsDownloading(false);
        }
    };

    // The backend returns the list most-recently-generated first.
    const latestReport = reports?.[0] ?? null;

    const downloadLatestReport = async () => {
        if (!latestReport) return;
        await downloadReport(latestReport.report_id);
    };

    return {
        reports,
        listError,
        isDownloading,
        downloadError,
        latestReport,
        hasReports: Boolean(reports?.length),
        isLoadingReports: reports === null && !listError,
        downloadReport,
        downloadLatestReport,
    };
}
