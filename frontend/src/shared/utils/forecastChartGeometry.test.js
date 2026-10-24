import { describe, expect, it } from "vitest";
import {
    buildChartGeometry,
    fullMonthLabel,
    shortMonthLabel,
    PLOT_X0,
    PLOT_X1,
    PLOT_Y_TOP,
    PLOT_Y_BOTTOM,
} from "./forecastChartGeometry.js";

const HISTORY = [
    { month: "2026-01", revenue: 100 },
    { month: "2026-02", revenue: 200 },
    { month: "2026-03", revenue: 300 },
];

describe("shortMonthLabel / fullMonthLabel", () => {
    it("formats a YYYY-MM string as a short month", () => {
        expect(shortMonthLabel("2026-01")).toBe("Jan");
        expect(shortMonthLabel("2026-12")).toBe("Dec");
    });

    it("formats a YYYY-MM string as a full month and year", () => {
        expect(fullMonthLabel("2026-01")).toBe("January 2026");
    });
});

describe("buildChartGeometry without a forecast", () => {
    const geometry = buildChartGeometry(HISTORY, null);

    it("plots one point per history month, oldest first", () => {
        expect(geometry.historyPoints).toHaveLength(3);
        expect(geometry.historyPoints[0].month).toBe("2026-01");
        expect(geometry.historyPoints[2].month).toBe("2026-03");
    });

    it("marks only the last point as the last actual", () => {
        expect(geometry.historyPoints.map((p) => p.isLastActual)).toEqual([
            false,
            false,
            true,
        ]);
    });

    it("keeps every point inside the plot area", () => {
        for (const p of geometry.historyPoints) {
            expect(p.x).toBeGreaterThanOrEqual(PLOT_X0);
            expect(p.x).toBeLessThanOrEqual(PLOT_X1);
            expect(p.y).toBeGreaterThanOrEqual(PLOT_Y_TOP);
            expect(p.y).toBeLessThanOrEqual(PLOT_Y_BOTTOM);
        }
    });

    it("has no forecast geometry", () => {
        expect(geometry.forecastPoint).toBeNull();
        expect(geometry.forecastLine).toBeNull();
        expect(geometry.forecastBand).toBeNull();
        expect(geometry.dividerX).toBeNull();
    });

    it("produces 4 grid lines", () => {
        expect(geometry.grid).toHaveLength(4);
    });
});

describe("buildChartGeometry with a forecast", () => {
    const forecast = {
        targetMonth: "2026-04",
        predictedRevenue: 400,
        interval: { lower: 350, upper: 450 },
    };
    const geometry = buildChartGeometry(HISTORY, forecast);

    it("places the forecast point after the last history point", () => {
        const lastHistoryX = geometry.historyPoints[2].x;
        expect(geometry.forecastPoint.x).toBeGreaterThan(lastHistoryX);
        expect(geometry.forecastPoint.month).toBe("2026-04");
    });

    it("draws a dashed connector from the last actual point to the forecast point", () => {
        expect(geometry.forecastLine).toContain(
            `${geometry.historyPoints[2].x},${geometry.historyPoints[2].y}`,
        );
        expect(geometry.forecastLine).toContain(
            `${geometry.forecastPoint.x},${geometry.forecastPoint.y}`,
        );
    });

    it("draws a confidence band anchored at the last actual point", () => {
        expect(geometry.forecastBand).not.toBeNull();
        expect(geometry.forecastBand.split(" ")).toHaveLength(3);
    });

    it("places the divider at the last actual point", () => {
        expect(geometry.dividerX).toBe(geometry.historyPoints[2].x);
    });

    it("appends a labeled forecast tick on the x-axis", () => {
        const last = geometry.xLabels[geometry.xLabels.length - 1];
        expect(last.isForecast).toBe(true);
        expect(last.label).toBe("Apr");
    });

    it("omits the confidence band when the model gives no interval", () => {
        const noInterval = buildChartGeometry(HISTORY, { ...forecast, interval: null });
        expect(noInterval.forecastBand).toBeNull();
        expect(noInterval.forecastPoint).not.toBeNull();
    });
});

describe("buildChartGeometry with a single history point", () => {
    it("does not divide by zero when there is only one point", () => {
        const geometry = buildChartGeometry([{ month: "2026-01", revenue: 100 }], null);
        expect(geometry.historyPoints).toHaveLength(1);
        expect(Number.isFinite(geometry.historyPoints[0].x)).toBe(true);
    });
});

describe("buildChartGeometry with no history", () => {
    it("returns an empty chart without throwing", () => {
        const geometry = buildChartGeometry([], null);
        expect(geometry.historyPoints).toEqual([]);
        expect(geometry.forecastPoint).toBeNull();
    });
});
