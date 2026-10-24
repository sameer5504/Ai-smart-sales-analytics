import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import GenerateReportButton from "./GenerateReportButton.jsx";
import { generateReport } from "../../services/reportsService";

vi.mock("../../services/reportsService", () => ({
    generateReport: vi.fn(),
}));

const DASHBOARD_DATA = {
    kpis: [{ label: "Total Revenue", value: "55,289 ILS" }],
};

const SAVED_REPORT = {
    report_id: "r1",
    user_id: 1,
    generated_at: "2026-09-03T10:00:00Z",
    data: DASHBOARD_DATA,
};

afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
});

describe("GenerateReportButton", () => {
    it("generates a report from the given data and notifies the caller", async () => {
        const user = userEvent.setup();
        const onGenerated = vi.fn();
        generateReport.mockResolvedValue(SAVED_REPORT);
        render(
            <GenerateReportButton data={DASHBOARD_DATA} onGenerated={onGenerated} />,
        );

        const button = screen.getByRole("button", { name: /generate report/i });
        await user.click(button);

        await waitFor(() =>
            expect(generateReport).toHaveBeenCalledWith(DASHBOARD_DATA),
        );
        await waitFor(() => expect(onGenerated).toHaveBeenCalledWith(SAVED_REPORT));
    });

    it("shows a pending state while generating and re-enables afterwards", async () => {
        const user = userEvent.setup();
        let resolveGenerate;
        generateReport.mockReturnValue(
            new Promise((resolve) => {
                resolveGenerate = resolve;
            }),
        );
        render(<GenerateReportButton data={DASHBOARD_DATA} />);

        const button = screen.getByRole("button", { name: /generate report/i });
        await user.click(button);

        expect(
            await screen.findByRole("button", { name: /generating/i }),
        ).toBeDisabled();

        resolveGenerate(SAVED_REPORT);

        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: /generate report/i }),
            ).toBeEnabled(),
        );
    });

    it("reports a failed generation and leaves the button usable", async () => {
        const user = userEvent.setup();
        generateReport.mockRejectedValue(
            new Error("Could not generate the report (500)."),
        );
        render(<GenerateReportButton data={DASHBOARD_DATA} />);

        const button = screen.getByRole("button", { name: /generate report/i });
        await user.click(button);

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Could not generate the report (500).",
        );
        expect(button).toBeEnabled();
    });

    it("ignores extra clicks while a generation is in flight", async () => {
        const user = userEvent.setup();
        let resolveGenerate;
        generateReport.mockReturnValue(
            new Promise((resolve) => {
                resolveGenerate = resolve;
            }),
        );
        render(<GenerateReportButton data={DASHBOARD_DATA} />);

        const button = screen.getByRole("button", { name: /generate report/i });
        await user.click(button);
        await user.click(button);

        resolveGenerate(SAVED_REPORT);
        await waitFor(() => expect(generateReport).toHaveBeenCalledTimes(1));
    });
});
