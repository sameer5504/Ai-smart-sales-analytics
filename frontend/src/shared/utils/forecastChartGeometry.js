// Pure layout math for the revenue forecast chart's SVG. Kept separate from
// the component so the coordinate logic can be unit-tested without
// rendering. Canvas size and margins follow the Dashboard design spec
// (viewBox 0 0 900 210, plot area x:[62,818] y:[30,175]).

export const VIEW_W = 900;
export const VIEW_H = 210;
export const PLOT_X0 = 62;
export const PLOT_X1 = 818;
export const PLOT_Y_TOP = 30;
export const PLOT_Y_BOTTOM = 175;
export const LABEL_Y = 196;

export function shortMonthLabel(monthStr) {
    const [year, month] = monthStr.split("-").map(Number);
    const date = new Date(Date.UTC(year, month - 1, 1));
    return new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(
        date,
    );
}

export function fullMonthLabel(monthStr) {
    const [year, month] = monthStr.split("-").map(Number);
    const date = new Date(Date.UTC(year, month - 1, 1));
    return new Intl.DateTimeFormat("en-US", {
        month: "long",
        year: "numeric",
        timeZone: "UTC",
    }).format(date);
}

function formatGridLabel(value) {
    if (Math.abs(value) >= 1000) return `${Math.round(value / 1000)}k`;
    return String(Math.round(value));
}

/**
 * Build the SVG coordinates for the chart from the forecast contract's
 * `history` array and, when the forecast is available, its
 * `predicted_revenue` / `interval` / `target_month`.
 *
 * @param {{month: string, revenue: number}[]} history oldest -> newest
 * @param {{targetMonth: string, predictedRevenue: number, interval: {lower: number, upper: number} | null} | null} forecast
 */
export function buildChartGeometry(history, forecast) {
    const L = history.length;
    const hasForecast = Boolean(forecast);
    const N = L + (hasForecast ? 1 : 0);

    const historyVals = history.map((p) => p.revenue);
    const allVals = hasForecast
        ? [
              ...historyVals,
              forecast.predictedRevenue,
              forecast.interval ? forecast.interval.lower : forecast.predictedRevenue,
              forecast.interval ? forecast.interval.upper : forecast.predictedRevenue,
          ]
        : historyVals;

    const maxV = allVals.length ? Math.max(...allVals) : 1;
    const minV = allVals.length ? Math.min(...allVals) : 0;
    const pad = (maxV - minV) * 0.2 || maxV * 0.12 || 1;
    const top = maxV + pad;
    const bot = Math.max(0, minV - pad);

    const Y = (v) =>
        top === bot
            ? (PLOT_Y_TOP + PLOT_Y_BOTTOM) / 2
            : PLOT_Y_BOTTOM - ((v - bot) / (top - bot)) * (PLOT_Y_BOTTOM - PLOT_Y_TOP);

    const X = (i) =>
        N > 1 ? PLOT_X0 + (i * (PLOT_X1 - PLOT_X0)) / (N - 1) : (PLOT_X0 + PLOT_X1) / 2;

    const historyPoints = history.map((p, i) => ({
        x: X(i),
        y: Y(p.revenue),
        month: p.month,
        revenue: p.revenue,
        isLastActual: i === L - 1,
        kind: "actual",
    }));

    const historyLine = historyPoints.map((p) => `${p.x},${p.y}`).join(" ");

    let forecastPoint = null;
    let forecastLine = null;
    let forecastBand = null;
    let dividerX = null;

    if (hasForecast && L > 0) {
        const lastX = X(L - 1);
        const lastY = Y(historyVals[L - 1]);
        forecastPoint = {
            x: X(L),
            y: Y(forecast.predictedRevenue),
            month: forecast.targetMonth,
            revenue: forecast.predictedRevenue,
            interval: forecast.interval,
            kind: "forecast",
        };
        forecastLine = `${lastX},${lastY} ${forecastPoint.x},${forecastPoint.y}`;
        if (forecast.interval) {
            forecastBand = `${lastX},${lastY} ${forecastPoint.x},${Y(forecast.interval.upper)} ${forecastPoint.x},${Y(forecast.interval.lower)}`;
        }
        dividerX = lastX;
    }

    const every = L > 0 ? Math.ceil(L / 9) : 1;
    const xLabels = history
        .map((p, i) => ({
            x: X(i),
            label: shortMonthLabel(p.month),
            emphasize: i === L - 1,
            show: L <= 10 || i % every === 0 || i === L - 1,
        }))
        .filter((l) => l.show);

    if (forecastPoint) {
        xLabels.push({
            x: forecastPoint.x,
            label: shortMonthLabel(forecastPoint.month),
            emphasize: true,
            isForecast: true,
            show: true,
        });
    }

    const grid = [0, 1, 2, 3].map((k) => {
        const value = bot + ((top - bot) * k) / 3;
        return { y: Y(value), value, label: formatGridLabel(value), baseline: k === 0 };
    });

    return {
        viewBox: `0 0 ${VIEW_W} ${VIEW_H}`,
        historyPoints,
        forecastPoint,
        historyLine,
        forecastLine,
        forecastBand,
        dividerX,
        grid,
        xLabels,
    };
}
