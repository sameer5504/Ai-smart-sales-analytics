import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FindingsPanel from "./FindingsPanel";

const navigate = vi.fn();

vi.mock("react-router-dom", async () => {
    const actual = await vi.importActual("react-router-dom");
    return { ...actual, useNavigate: () => navigate };
});

vi.mock("../services/recommendationsService", () => ({
    fetchRecommendations: vi.fn(),
}));

const { fetchRecommendations } = await import("../services/recommendationsService");

function withFindings(severities) {
    return {
        status: "available",
        recommendations: severities.map((severity) => ({
            finding: { severity },
        })),
        total_findings: severities.length,
        suppressed_count: 0,
        message: null,
    };
}

function draw() {
    render(
        <MemoryRouter>
            <FindingsPanel datasetId={7} />
        </MemoryRouter>,
    );
}

beforeEach(() => {
    navigate.mockReset();
    fetchRecommendations.mockReset();
});

describe("FindingsPanel", () => {
    it("asks for the recommendations belonging to the dataset it was given", async () => {
        fetchRecommendations.mockResolvedValue(withFindings(["critical"]));

        draw();

        await waitFor(() => expect(fetchRecommendations).toHaveBeenCalledWith(7));
    });

    it("counts the findings and marks the urgent ones", async () => {
        fetchRecommendations.mockResolvedValue(
            withFindings(["critical", "warning", "info"]),
        );

        draw();

        expect(
            await screen.findByText("3 findings need your attention"),
        ).toBeInTheDocument();
        expect(screen.getByText("1 critical")).toBeInTheDocument();
        expect(screen.getByText("1 warning")).toBeInTheDocument();
        expect(screen.getByText("1 to know")).toBeInTheDocument();
    });

    it("opens the assistant carrying the question with it", async () => {
        fetchRecommendations.mockResolvedValue(withFindings(["critical", "warning"]));

        draw();

        const button = await screen.findByRole("button", {
            name: /open in the assistant/i,
        });

        await userEvent.click(button);

        expect(navigate).toHaveBeenCalledWith("/assistant", {
            state: { prompt: "Walk me through the 2 findings, most serious first" },
        });
    });

    it("says the question will not be sent on its own", async () => {
        fetchRecommendations.mockResolvedValue(withFindings(["critical"]));

        draw();

        expect(await screen.findByText(/already typed, unsent/i)).toBeInTheDocument();
    });

    it("offers no way in when there is nothing to say", async () => {
        fetchRecommendations.mockResolvedValue({
            status: "unavailable",
            recommendations: [],
            reason: "no_findings",
            message: "Your numbers look steady.",
        });

        draw();

        expect(
            await screen.findByText("Nothing stands out in your data"),
        ).toBeInTheDocument();
        expect(screen.getByText("Your numbers look steady.")).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: /open in the assistant/i }),
        ).not.toBeInTheDocument();
    });

    it("stays out of the way when the dataset has no recommendations to load", async () => {
        fetchRecommendations.mockRejectedValue(new Error("No prepared data"));

        const { container } = render(
            <MemoryRouter>
                <FindingsPanel datasetId={99} />
            </MemoryRouter>,
        );

        await waitFor(() => expect(container).toBeEmptyDOMElement());
    });
    it("does not tell the user their data is fine when the check failed", async () => {
        fetchRecommendations.mockResolvedValue({
            status: "unavailable",
            recommendations: [],
            reason: "detection_unavailable",
            message: "Something broke on our side.",
        });

        draw();

        expect(
            await screen.findByText("We could not check your data this time"),
        ).toBeInTheDocument();
        expect(
            screen.queryByText("Nothing stands out in your data"),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: /open in the assistant/i }),
        ).not.toBeInTheDocument();
    });

    it("shows what the most urgent finding actually says", async () => {
        fetchRecommendations.mockResolvedValue({
            status: "available",
            recommendations: [
                {
                    finding: {
                        severity: "critical",
                        message: "Coffee 250g sold 65% below its usual week.",
                    },
                    action: "Check Coffee 250g.",
                },
            ],
            total_findings: 1,
            suppressed_count: 0,
        });

        draw();

        expect(
            await screen.findByText("Coffee 250g sold 65% below its usual week."),
        ).toBeInTheDocument();
    });

    it("gives the strip a heading a screen reader can find", async () => {
        fetchRecommendations.mockResolvedValue(withFindings(["critical"]));

        draw();

        expect(
            await screen.findByRole("heading", { name: /needs your attention/i }),
        ).toBeInTheDocument();
    });
});
