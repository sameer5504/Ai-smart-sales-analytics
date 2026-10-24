import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ReportDownloadButton from "./ReportDownloadButton.jsx";
import { fetchReport, fetchReports } from "../../services/reportsService";

vi.mock("../../services/reportsService", () => ({
    fetchReports: vi.fn(),
    fetchReport: vi.fn(),
}));

const REPORTS = [
    { report_id: "b2", user_id: 1, generated_at: "2026-08-30T10:15:00Z" },
    { report_id: "a1", user_id: 1, generated_at: "2026-08-01T09:00:00Z" },
];

const FULL_REPORT = { ...REPORTS[0], data: { total_revenue: 1234 } };

let clickedLink;

beforeEach(() => {
    clickedLink = null;
    // jsdom/happy-dom can't perform a real download, so capture the anchor
    // the hook creates and assert on what it would have saved.
    globalThis.URL.createObjectURL = vi.fn(() => "blob:report");
    globalThis.URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function () {
        clickedLink = { href: this.href, download: this.download };
    });
});

afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
});

describe("ReportDownloadButton", () => {
    it("downloads the most recent report and names the file after it", async () => {
        const user = userEvent.setup();
        fetchReports.mockResolvedValue(REPORTS);
        fetchReport.mockResolvedValue(FULL_REPORT);
        render(<ReportDownloadButton />);

        const button = await screen.findByRole("button", { name: /download report/i });
        await waitFor(() => expect(button).toBeEnabled());

        await user.click(button);

        // The list comes back most-recent-first, so the top one is taken.
        await waitFor(() => expect(fetchReport).toHaveBeenCalledWith("b2"));
        expect(clickedLink).toEqual({
            href: "blob:report",
            download: "report-b2.json",
        });
    });

    it("stays disabled and says so when there are no reports yet", async () => {
        fetchReports.mockResolvedValue([]);
        render(<ReportDownloadButton />);

        expect(await screen.findByText("No reports saved yet.")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /download report/i })).toBeDisabled();
        expect(fetchReport).not.toHaveBeenCalled();
    });

    it("reports a failure to list reports without crashing", async () => {
        fetchReports.mockRejectedValue(new Error("Network error: could not reach"));
        render(<ReportDownloadButton />);

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Network error: could not reach",
        );
        expect(screen.getByRole("button", { name: /download report/i })).toBeDisabled();
    });

    it("reports a failed download and leaves the button usable", async () => {
        const user = userEvent.setup();
        fetchReports.mockResolvedValue(REPORTS);
        fetchReport.mockRejectedValue(new Error("That report is no longer available."));
        render(<ReportDownloadButton />);

        const button = await screen.findByRole("button", { name: /download report/i });
        await waitFor(() => expect(button).toBeEnabled());

        await user.click(button);

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "That report is no longer available.",
        );
        expect(button).toBeEnabled();
        expect(clickedLink).toBeNull();
    });

    it("ignores extra clicks while a download is in flight", async () => {
        const user = userEvent.setup();
        fetchReports.mockResolvedValue(REPORTS);
        let resolveReport;
        fetchReport.mockReturnValue(
            new Promise((resolve) => {
                resolveReport = resolve;
            }),
        );
        render(<ReportDownloadButton />);

        const button = await screen.findByRole("button", { name: /download report/i });
        await waitFor(() => expect(button).toBeEnabled());

        await user.click(button);
        expect(
            await screen.findByRole("button", { name: /preparing download/i }),
        ).toBeDisabled();

        resolveReport(FULL_REPORT);
        await waitFor(() => expect(fetchReport).toHaveBeenCalledTimes(1));
    });
});
