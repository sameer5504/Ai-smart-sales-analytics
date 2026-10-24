import { useForecast } from "../hooks/useForecast.js";
import {
    fullMonthLabel,
    LABEL_Y,
    PLOT_X0,
    PLOT_X1,
    PLOT_Y_BOTTOM,
    PLOT_Y_TOP,
    VIEW_H,
    VIEW_W,
} from "../../../shared/utils/forecastChartGeometry.js";

// Which model produced the forecast is implementation detail, so the normal
// case says nothing. Only the fallback is labelled: if the Azure ML endpoint
// could not answer, the built-in model did, and the number is a little less
// accurate. A value with no entry here is not shown at all - a raw identifier
// from the API is not something to put in front of a user.
const MODEL_LABELS = {
    trained_revenue: "Built-in model",
};

function formatAmount(value, currency) {
    if (value == null || Number.isNaN(value)) return "";
    const options = currency
        ? { style: "currency", currency, maximumFractionDigits: 0 }
        : { maximumFractionDigits: 0 };
    return new Intl.NumberFormat("en-US", options).format(value);
}

// Renders the revenue forecast chart for a previously uploaded file. All
// data-fetching and derived-state logic lives in useForecast(); this
// component only turns that state into markup.
function ForecastChart({ datasetId }) {
    const {
        status,
        errorMessage,
        data,
        isAvailable,
        geometry,
        hasHistory,
        activePoint,
        setActiveKey,
    } = useForecast(datasetId);

    if (!datasetId) return null;

    if (status === "loading") {
        return (
            <div style={styles.card}>
                <div style={styles.skeletonTitle} aria-hidden="true" />
                <div style={styles.skeletonChart} aria-hidden="true" />
                <span style={styles.srOnly}>Loading revenue forecast…</span>
            </div>
        );
    }

    if (status === "error") {
        return (
            <div style={styles.card} role="alert">
                <div style={styles.headerRow}>
                    <h3 style={styles.title}>Revenue forecast</h3>
                </div>
                <div style={styles.unavailableValue}>Unavailable</div>
                <div style={styles.reason}>
                    {errorMessage || "Could not load the forecast."}
                </div>
            </div>
        );
    }

    if (status === "invalid") {
        return (
            <div style={styles.card} role="alert">
                <div style={styles.headerRow}>
                    <h3 style={styles.title}>Revenue forecast</h3>
                </div>
                <div style={styles.unavailableValue}>Unavailable</div>
                <div style={styles.reason}>
                    The server response didn&rsquo;t include the data this chart needs.
                </div>
            </div>
        );
    }

    if (!hasHistory) {
        return (
            <div style={styles.card}>
                <div style={styles.headerRow}>
                    <h3 style={styles.title}>Revenue forecast</h3>
                    <span style={styles.badge}>Unavailable</span>
                </div>
                <p style={styles.reason}>
                    {data.message || "No sales history is available to chart yet."}
                </p>
                <div style={styles.emptyBox}>No forecast data to show</div>
            </div>
        );
    }

    const chartLabel = geometry.forecastPoint
        ? "Revenue over the selected range continuing as a dashed forecast inside a hatched confidence band"
        : "Revenue over the selected range";

    return (
        <div style={styles.card}>
            <div style={styles.headerRow}>
                <div>
                    <div style={styles.headerTop}>
                        <h3 style={styles.title}>
                            {isAvailable
                                ? `Forecast · ${fullMonthLabel(data.target_month)} revenue`
                                : "Revenue forecast"}
                        </h3>
                        {isAvailable && MODEL_LABELS[data.model] && (
                            <span style={styles.modelBadge}>
                                {MODEL_LABELS[data.model]}
                            </span>
                        )}
                        {!isAvailable && <span style={styles.badge}>Unavailable</span>}
                    </div>
                    {isAvailable ? (
                        <div style={styles.valueRow}>
                            <span style={styles.value}>
                                {formatAmount(data.predicted_revenue, data.currency)}
                            </span>
                            {data.interval && (
                                <span style={styles.rangeText}>
                                    likely between{" "}
                                    {formatAmount(data.interval.lower, data.currency)}{" "}
                                    and{" "}
                                    {formatAmount(data.interval.upper, data.currency)}
                                </span>
                            )}
                        </div>
                    ) : (
                        <p style={styles.reason}>{data.message}</p>
                    )}
                </div>
            </div>

            <svg
                viewBox={geometry.viewBox}
                style={styles.svg}
                role="img"
                aria-label={chartLabel}
                onMouseLeave={() => setActiveKey(null)}
            >
                <defs>
                    <pattern
                        id="forecastHatch"
                        width="7"
                        height="7"
                        patternTransform="rotate(45)"
                        patternUnits="userSpaceOnUse"
                    >
                        <line
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="7"
                            stroke="var(--chart-1)"
                            strokeWidth="1.6"
                            strokeOpacity="0.3"
                        />
                    </pattern>
                </defs>

                {geometry.grid.map((g) => (
                    <g key={g.value}>
                        <line
                            x1={PLOT_X0}
                            y1={g.y}
                            x2={PLOT_X1}
                            y2={g.y}
                            stroke={g.baseline ? "var(--n-400)" : "var(--n-100)"}
                            strokeWidth="1"
                        />
                        <text
                            x={PLOT_X0 - 6}
                            y={g.y}
                            dy="4"
                            textAnchor="end"
                            fontFamily="IBM Plex Mono, monospace"
                            fontSize="10.5"
                            fill="var(--n-400)"
                        >
                            {g.label}
                        </text>
                    </g>
                ))}

                {geometry.forecastBand && (
                    <polygon
                        points={geometry.forecastBand}
                        fill="url(#forecastHatch)"
                    />
                )}

                <polyline
                    points={geometry.historyLine}
                    fill="none"
                    stroke="var(--chart-1)"
                    strokeWidth="2.75"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                />

                {geometry.forecastLine && (
                    <polyline
                        points={geometry.forecastLine}
                        fill="none"
                        stroke="var(--chart-1)"
                        strokeWidth="2.75"
                        strokeDasharray="9 6"
                        strokeLinecap="round"
                    />
                )}

                {geometry.dividerX != null && (
                    <line
                        x1={geometry.dividerX}
                        y1={PLOT_Y_TOP - 6}
                        x2={geometry.dividerX}
                        y2={PLOT_Y_BOTTOM}
                        stroke="var(--n-300)"
                        strokeWidth="1"
                        strokeDasharray="4 4"
                    />
                )}

                {geometry.historyPoints.map((p) => (
                    <circle
                        key={p.month}
                        cx={p.x}
                        cy={p.y}
                        r={p.isLastActual ? 4.5 : 3.5}
                        fill={p.isLastActual ? "var(--chart-1)" : "var(--n-0)"}
                        stroke="var(--chart-1)"
                        strokeWidth={p.isLastActual ? 0 : 2}
                        tabIndex={0}
                        role="img"
                        aria-label={`${fullMonthLabel(p.month)}: ${formatAmount(p.revenue, data.currency)}, actual`}
                        style={styles.point}
                        onMouseEnter={() => setActiveKey(p.month)}
                        onFocus={() => setActiveKey(p.month)}
                        onBlur={() => setActiveKey(null)}
                    />
                ))}

                {geometry.forecastPoint && (
                    <circle
                        cx={geometry.forecastPoint.x}
                        cy={geometry.forecastPoint.y}
                        r={5}
                        fill="var(--n-0)"
                        stroke="var(--chart-1)"
                        strokeWidth={2.5}
                        strokeDasharray="3 2"
                        tabIndex={0}
                        role="img"
                        aria-label={`${fullMonthLabel(geometry.forecastPoint.month)}: forecast ${formatAmount(geometry.forecastPoint.revenue, data.currency)}${
                            geometry.forecastPoint.interval
                                ? `, likely between ${formatAmount(geometry.forecastPoint.interval.lower, data.currency)} and ${formatAmount(geometry.forecastPoint.interval.upper, data.currency)}`
                                : ""
                        }`}
                        style={styles.point}
                        onMouseEnter={() => setActiveKey(geometry.forecastPoint.month)}
                        onFocus={() => setActiveKey(geometry.forecastPoint.month)}
                        onBlur={() => setActiveKey(null)}
                    />
                )}

                {geometry.xLabels.map((l) => (
                    <text
                        key={`${l.label}-${l.x}`}
                        x={l.x}
                        y={LABEL_Y}
                        textAnchor="middle"
                        fontFamily="IBM Plex Mono, monospace"
                        fontSize="10.5"
                        fill={
                            l.isForecast
                                ? "var(--chart-1)"
                                : l.emphasize
                                  ? "var(--n-700)"
                                  : "var(--n-400)"
                        }
                    >
                        {l.label}
                    </text>
                ))}
            </svg>

            {activePoint && (
                <div
                    style={{
                        ...styles.tooltip,
                        left: `${(activePoint.x / VIEW_W) * 100}%`,
                        top: `${(activePoint.y / VIEW_H) * 100}%`,
                    }}
                    role="status"
                >
                    <div style={styles.tooltipMonth}>
                        {fullMonthLabel(activePoint.month)}
                    </div>
                    <div style={styles.tooltipValue}>
                        {formatAmount(activePoint.revenue, data.currency)}
                    </div>
                    <div style={styles.tooltipKind}>
                        {activePoint.kind === "forecast" ? "Forecast" : "Actual"}
                    </div>
                    {activePoint.kind === "forecast" && activePoint.interval && (
                        <div style={styles.tooltipRange}>
                            likely between{" "}
                            {formatAmount(activePoint.interval.lower, data.currency)}{" "}
                            and{" "}
                            {formatAmount(activePoint.interval.upper, data.currency)}
                        </div>
                    )}
                </div>
            )}

            <div style={styles.legend}>
                <span style={styles.legendItem}>
                    <span style={styles.legendDotSolid} /> Actual
                </span>
                {geometry.forecastPoint && (
                    <>
                        <span style={styles.legendItem}>
                            <span style={styles.legendDotDashed} /> Forecast
                        </span>
                        {geometry.forecastBand && (
                            <span style={styles.legendItem}>
                                <span style={styles.legendSwatchHatch} /> Confidence
                                range
                            </span>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

const styles = {
    card: {
        background: "var(--n-0)",
        border: "1px solid var(--n-100)",
        borderRadius: "var(--r-lg)",
        boxShadow: "var(--e1)",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        position: "relative",
    },
    headerRow: {
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "24px",
        flexWrap: "wrap",
    },
    headerTop: {
        display: "flex",
        alignItems: "center",
        gap: "10px",
        flexWrap: "wrap",
        marginBottom: "6px",
    },
    title: {
        margin: 0,
        fontFamily: "var(--font-latin)",
        fontWeight: 600,
        fontSize: "16px",
    },
    modelBadge: {
        fontFamily: "var(--font-mono)",
        fontWeight: 500,
        fontSize: "10.5px",
        letterSpacing: ".04em",
        textTransform: "uppercase",
        color: "var(--n-500)",
        background: "var(--n-50)",
        border: "1px solid var(--n-100)",
        borderRadius: "var(--r-full)",
        padding: "4px 7px",
    },
    badge: {
        fontFamily: "var(--font-mono)",
        fontWeight: 500,
        fontSize: "10.5px",
        letterSpacing: ".04em",
        textTransform: "uppercase",
        color: "var(--n-600)",
        background: "var(--n-50)",
        border: "1px solid var(--n-100)",
        borderRadius: "var(--r-full)",
        padding: "4px 7px",
    },
    valueRow: {
        display: "flex",
        alignItems: "baseline",
        gap: "12px",
        flexWrap: "wrap",
    },
    value: {
        fontFamily: "var(--font-latin)",
        fontWeight: 600,
        fontSize: "32px",
        lineHeight: 1,
        letterSpacing: "-.015em",
        color: "var(--n-800)",
        fontVariantNumeric: "tabular-nums lining-nums",
    },
    rangeText: {
        fontFamily: "var(--font-latin)",
        fontSize: "14px",
        color: "var(--n-500)",
        fontVariantNumeric: "tabular-nums",
    },
    reason: {
        margin: 0,
        fontFamily: "var(--font-latin)",
        fontSize: "13.5px",
        lineHeight: 1.6,
        color: "var(--n-600)",
    },
    svg: {
        width: "100%",
        height: "auto",
        display: "block",
    },
    point: {
        cursor: "pointer",
        outline: "none",
    },
    tooltip: {
        position: "absolute",
        transform: "translate(-50%, -120%)",
        background: "var(--n-800)",
        color: "var(--n-0)",
        borderRadius: "var(--r-md)",
        padding: "8px 10px",
        fontFamily: "var(--font-latin)",
        fontSize: "12.5px",
        lineHeight: 1.45,
        boxShadow: "var(--e2)",
        pointerEvents: "none",
        whiteSpace: "nowrap",
        zIndex: 1,
    },
    tooltipMonth: {
        fontWeight: 600,
    },
    tooltipValue: {
        fontVariantNumeric: "tabular-nums",
    },
    tooltipKind: {
        color: "var(--n-300)",
        fontSize: "11px",
        textTransform: "uppercase",
        letterSpacing: ".04em",
    },
    tooltipRange: {
        color: "var(--n-300)",
        fontSize: "11px",
    },
    legend: {
        display: "flex",
        alignItems: "center",
        gap: "18px",
        flexWrap: "wrap",
        fontFamily: "var(--font-latin)",
        fontSize: "12px",
        color: "var(--n-500)",
    },
    legendItem: {
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
    },
    legendDotSolid: {
        width: "9px",
        height: "9px",
        borderRadius: "50%",
        background: "var(--chart-1)",
        display: "inline-block",
    },
    legendDotDashed: {
        width: "9px",
        height: "9px",
        borderRadius: "50%",
        background: "var(--n-0)",
        border: "1.5px dashed var(--chart-1)",
        display: "inline-block",
    },
    legendSwatchHatch: {
        width: "14px",
        height: "9px",
        borderRadius: "2px",
        background:
            "repeating-linear-gradient(45deg, var(--chart-1) 0, var(--chart-1) 1.5px, transparent 1.5px, transparent 5px)",
        opacity: 0.55,
        display: "inline-block",
    },
    unavailableValue: {
        fontFamily: "var(--font-latin)",
        fontWeight: 500,
        fontSize: "20px",
        color: "var(--n-400)",
    },
    emptyBox: {
        border: "1px dashed var(--n-200)",
        borderRadius: "var(--r-md)",
        background: "var(--n-25)",
        height: "132px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "var(--font-latin)",
        fontSize: "13px",
        color: "var(--n-400)",
    },
    skeletonTitle: {
        height: "18px",
        width: "40%",
        borderRadius: "var(--r-sm)",
        background: "var(--n-100)",
    },
    skeletonChart: {
        height: "180px",
        width: "100%",
        borderRadius: "var(--r-md)",
        background: "var(--n-50)",
    },
    srOnly: {
        position: "absolute",
        width: "1px",
        height: "1px",
        overflow: "hidden",
        clip: "rect(0 0 0 0)",
    },
};

export default ForecastChart;
