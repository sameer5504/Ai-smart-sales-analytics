import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForecastChart from "./ForecastChart.jsx";
import { fetchRevenueForecast } from "../services/forecastService.js";

vi.mock("../services/forecastService.js", () => ({
    fetchRevenueForecast: vi.fn(),
}));

const AVAILABLE_RESPONSE = {
    status: "available",
    target_month: "2026-04",
    predicted_revenue: 400,
    currency: null,
    model: "trained_revenue",
    history: [
        { month: "2026-01", revenue: 100 },
        { month: "2026-02", revenue: 200 },
        { month: "2026-03", revenue: 300 },
    ],
    interval: { lower: 350, upper: 450 },
    reason: null,
    message: null,
    generated_at: "2026-03-01T12:00:00+00:00",
};

const UNAVAILABLE_WITH_HISTORY = {
    status: "unavailable",
    target_month: "2026-02",
    predicted_revenue: null,
    currency: null,
    model: null,
    history: [{ month: "2026-01", revenue: 100 }],
    interval: null,
    reason: "insufficient_history",
    message: "Need at least 28 days of history to forecast; found 12.",
    generated_at: "2026-03-01T12:00:00+00:00",
};

const UNAVAILABLE_NO_HISTORY = {
    status: "unavailable",
    target_month: "1970-01",
    predicted_revenue: null,
    currency: null,
    model: null,
    history: [],
    interval: null,
    reason: "model_unavailable",
    message: "The forecasting model is not available right now.",
    generated_at: "2026-03-01T12:00:00+00:00",
};

describe("ForecastChart", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders nothing until a dataset is selected", () => {
        const { container } = render(<ForecastChart datasetId={null} />);
        expect(container).toBeEmptyDOMElement();
        expect(fetchRevenueForecast).not.toHaveBeenCalled();
    });

    it("shows a loading state before the response arrives", () => {
        fetchRevenueForecast.mockReturnValue(new Promise(() => {})); // never resolves
        render(<ForecastChart datasetId={1} />);
        expect(screen.getByText(/Loading revenue forecast/i)).toBeInTheDocument();
    });

    it("renders the forecast title, value, range and model label when available", async () => {
        fetchRevenueForecast.mockResolvedValue(AVAILABLE_RESPONSE);
        render(<ForecastChart datasetId={1} />);

        expect(
            await screen.findByText("Forecast · April 2026 revenue"),
        ).toBeInTheDocument();
        expect(screen.getByText("400")).toBeInTheDocument();
        expect(screen.getByText(/likely between 350 and 450/)).toBeInTheDocument();
        expect(screen.getByText("Built-in model")).toBeInTheDocument();
    });

    it("says nothing about the model when the Azure endpoint answered", async () => {
        fetchRevenueForecast.mockResolvedValue({
            ...AVAILABLE_RESPONSE,
            model: "automl_endpoint",
        });
        render(<ForecastChart datasetId={1} />);

        await screen.findByText(/Forecast ·/);

        expect(screen.queryByText("Built-in model")).not.toBeInTheDocument();
        expect(screen.queryByText("automl_endpoint")).not.toBeInTheDocument();
        expect(fetchRevenueForecast).toHaveBeenCalledWith(1);
    });

    it("draws a point per history month plus one forecast point", async () => {
        fetchRevenueForecast.mockResolvedValue(AVAILABLE_RESPONSE);
        const { container } = render(<ForecastChart datasetId={1} />);

        await screen.findByText("Forecast · April 2026 revenue");
        const circles = container.querySelectorAll("circle");
        expect(circles).toHaveLength(4); // 3 history + 1 forecast
    });

    it("shows a tooltip with the exact value and period on hover", async () => {
        fetchRevenueForecast.mockResolvedValue(AVAILABLE_RESPONSE);
        const { container } = render(<ForecastChart datasetId={1} />);

        await screen.findByText("Forecast · April 2026 revenue");
        const firstPoint = container.querySelector("circle");
        fireEvent.mouseEnter(firstPoint);

        const tooltip = await screen.findByRole("status");
        expect(within(tooltip).getByText("January 2026")).toBeInTheDocument();
        expect(within(tooltip).getByText("100")).toBeInTheDocument();
        expect(within(tooltip).getByText("Actual")).toBeInTheDocument();
    });

    it("shows the Unavailable treatment but still draws the history line when some history exists", async () => {
        fetchRevenueForecast.mockResolvedValue(UNAVAILABLE_WITH_HISTORY);
        const { container } = render(<ForecastChart datasetId={1} />);

        expect(await screen.findByText(/Need at least 28 days/)).toBeInTheDocument();
        expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
        expect(container.querySelectorAll("circle")).toHaveLength(1); // just the one history point
        expect(container.querySelector("svg")).toBeInTheDocument();
    });

    it("shows a dashed empty-state box and no chart when there is no history at all", async () => {
        fetchRevenueForecast.mockResolvedValue(UNAVAILABLE_NO_HISTORY);
        render(<ForecastChart datasetId={1} />);

        expect(await screen.findByText("No forecast data to show")).toBeInTheDocument();
        expect(
            screen.queryByRole("img", { name: /Revenue over/i }),
        ).not.toBeInTheDocument();
    });

    it("shows a network/server error distinctly from the unavailable state", async () => {
        fetchRevenueForecast.mockRejectedValue(
            new Error("Network error: could not reach the server."),
        );
        render(<ForecastChart datasetId={1} />);

        expect(await screen.findByRole("alert")).toHaveTextContent("Network error");
    });

    it("shows an invalid-data state instead of crashing on a malformed response", async () => {
        fetchRevenueForecast.mockResolvedValue({ oops: "not the contract shape" });
        render(<ForecastChart datasetId={1} />);

        expect(await screen.findByRole("alert")).toHaveTextContent(
            /didn.t include the data/i,
        );
    });

    it("refetches when the dataset changes", async () => {
        fetchRevenueForecast.mockResolvedValue(AVAILABLE_RESPONSE);
        const { rerender } = render(<ForecastChart datasetId={1} />);
        await screen.findByText("Forecast · April 2026 revenue");

        rerender(<ForecastChart datasetId={2} />);
        expect(fetchRevenueForecast).toHaveBeenCalledWith(2);
        await waitFor(() => expect(fetchRevenueForecast).toHaveBeenCalledTimes(2));
    });
});
