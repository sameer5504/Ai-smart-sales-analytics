import { useState } from "react";
import "./SalesPerformanceChart.css";

const METRICS = {
    total_revenue: {
        label: "Total Revenue",
    },
    units_sold: {
        label: "Units Sold",
    },
    order_count: {
        label: "Order Count",
    },
};

const GRANULARITY_UNIT = {
    daily: "Day",
    weekly: "Week",
    monthly: "Month",
};

// Below this many points, every single one gets its own x-axis label - at
// or under a year of months, ~3 months of weeks, under 2 weeks of days,
// skipping any of them would read as a mistake (see DENSE_LABEL_THRESHOLD).
// Above it, MAX_TICKS evenly-spaced labels are shown instead of cramming
// every point in - e.g. 52 weeks becomes "Week 1, 12, 23, 34, 45, 52"
// rather than "Week 1, 26, 52" (too sparse/uneven) or all 52 (too crowded).
const DENSE_LABEL_THRESHOLD = 12;
const MAX_TICKS = 6;

function shortAxisLabel(index, granularity) {
    const unit = GRANULARITY_UNIT[granularity] || "Period";
    return `${unit} ${index + 1}`;
}

// Picks up to maxTicks indices spread evenly across [0, pointCount - 1],
// always including the first and last point so the axis's actual start and
// end are never left unlabeled.
function evenlySpacedTickIndices(pointCount, maxTicks) {
    if (pointCount <= maxTicks) {
        return Array.from({ length: pointCount }, (_, i) => i);
    }

    const step = Math.ceil((pointCount - 1) / (maxTicks - 1));
    const indices = [];
    for (let i = 0; i < pointCount - 1; i += step) {
        indices.push(i);
    }
    indices.push(pointCount - 1);
    return indices;
}

function SalesPerformanceChart({ data, metric, onMetricChange, granularity }) {
    const [hoverIndex, setHoverIndex] = useState(null);

    if (!data.length) {
        return null;
    }

    const width = 900;
    const height = 260;

    const values = data.map((point) => Number(point[metric]) || 0);
    const maxValue = Math.max(...values, 1);

    const formatNumber = (value) =>
        new Intl.NumberFormat("en-US", {
            maximumFractionDigits: 2,
        }).format(value);

    // Left padding scales with the widest y-axis label that will actually be
    // drawn (the top gridline, at maxValue) instead of a fixed guess - a
    // fixed value clipped long numbers like "140.25" against the left edge.
    const maxLabelChars = formatNumber(maxValue).length;
    const yAxisLabelWidth = Math.max(40, maxLabelChars * 8);

    const padding = {
        top: 18,
        right: 18,
        bottom: 44,
        left: yAxisLabelWidth + 24,
    };

    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const points = data.map((point, index) => {
        const x =
            data.length === 1
                ? padding.left + chartWidth / 2
                : padding.left + (index / (data.length - 1)) * chartWidth;

        const y =
            padding.top +
            chartHeight -
            ((Number(point[metric]) || 0) / maxValue) * chartHeight;

        return {
            x,
            y,
            period: point.period,
            label: point.label || point.period,
            value: Number(point[metric]) || 0,
        };
    });

    const polylinePoints = points.map((point) => `${point.x},${point.y}`).join(" ");

    const areaPoints = `${padding.left},${padding.top + chartHeight} ${polylinePoints} ${
        padding.left + chartWidth
    },${padding.top + chartHeight}`;

    const firstIndex = 0;
    const lastIndex = points.length - 1;

    const gridRatios = [1, 0.75, 0.5, 0.25, 0];

    const hoveredPoint = hoverIndex !== null ? points[hoverIndex] : null;

    // Tooltip anchors above the point normally, but flips below it when the
    // point sits too close to the chart's top edge (e.g. the highest peak),
    // and flips its horizontal anchor near the left/right edges - otherwise
    // it renders partly outside the chart and gets clipped.
    let tooltipTransformX = "-50%";
    if (hoveredPoint) {
        if (hoverIndex === firstIndex && points.length > 1) {
            tooltipTransformX = "0";
        } else if (hoverIndex === lastIndex && points.length > 1) {
            tooltipTransformX = "-100%";
        }
    }
    const nearTopEdge = hoveredPoint && hoveredPoint.y - padding.top < 60;
    const tooltipTransformY = nearTopEdge ? "18px" : "calc(-100% - 14px)";
    const tooltipTransform = `translate(${tooltipTransformX}, ${tooltipTransformY})`;

    const tickIndices =
        points.length <= DENSE_LABEL_THRESHOLD
            ? Array.from({ length: points.length }, (_, i) => i)
            : evenlySpacedTickIndices(points.length, MAX_TICKS);

    return (
        <section className="sales-chart-section">
            <div className="sales-chart-header">
                <div className="sales-chart-heading">
                    <h2>Performance Over Time</h2>
                    <p>{METRICS[metric].label}</p>
                </div>

                <div
                    className="sales-chart-metric-group"
                    role="group"
                    aria-label="Metric"
                >
                    {Object.entries(METRICS).map(([key, meta]) => {
                        const isActive = metric === key;

                        return (
                            <button
                                key={key}
                                type="button"
                                className={`sales-chart-metric-button ${
                                    isActive ? "sales-chart-metric-button-active" : ""
                                }`}
                                onClick={() => onMetricChange(key)}
                                aria-pressed={isActive}
                            >
                                {meta.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            <div className="sales-chart-container" style={{ position: "relative" }}>
                <svg
                    viewBox={`0 0 ${width} ${height}`}
                    role="img"
                    aria-label={`${METRICS[metric].label} over time`}
                >
                    <defs>
                        <linearGradient
                            id="salesChartAreaFill"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                        >
                            <stop
                                offset="0%"
                                stopColor="var(--chart-1)"
                                stopOpacity="0.28"
                            />
                            <stop
                                offset="100%"
                                stopColor="var(--chart-1)"
                                stopOpacity="0"
                            />
                        </linearGradient>
                    </defs>

                    {gridRatios.map((ratio) => {
                        const y = padding.top + (1 - ratio) * chartHeight;
                        const value = maxValue * ratio;

                        return (
                            <g key={ratio}>
                                <line
                                    x1={padding.left}
                                    y1={y}
                                    x2={padding.left + chartWidth}
                                    y2={y}
                                    className="sales-chart-grid-line"
                                />
                                <text
                                    x={padding.left - 10}
                                    y={y}
                                    textAnchor="end"
                                    dominantBaseline="middle"
                                    className="sales-chart-grid-label"
                                >
                                    {formatNumber(value)}
                                </text>
                            </g>
                        );
                    })}

                    <polygon
                        key={`area-${metric}`}
                        points={areaPoints}
                        className="sales-chart-area"
                    />

                    <polyline
                        key={`line-${metric}`}
                        points={polylinePoints}
                        className="sales-chart-line"
                    />

                    {/* Vertical guide line following the hovered point, drawn
                        under the points so it doesn't obscure them. */}
                    {hoveredPoint && (
                        <line
                            x1={hoveredPoint.x}
                            y1={padding.top}
                            x2={hoveredPoint.x}
                            y2={padding.top + chartHeight}
                            className="sales-chart-hover-guide"
                        />
                    )}

                    {points.map((point, index) => {
                        const isHovered = hoverIndex === index;
                        return (
                            <g key={`${point.period}-${metric}`}>
                                <circle
                                    cx={point.x}
                                    cy={point.y}
                                    r={isHovered ? 6 : 3.5}
                                    className={
                                        isHovered
                                            ? "sales-chart-point sales-chart-point-active"
                                            : "sales-chart-point"
                                    }
                                    style={{ animationDelay: `${index * 30}ms` }}
                                />
                                {/* Wider, invisible hit area - the visible dot
                                    (r=3.5) is too small a target to hover
                                    comfortably on its own. */}
                                <circle
                                    cx={point.x}
                                    cy={point.y}
                                    r="14"
                                    fill="transparent"
                                    style={{ cursor: "pointer" }}
                                    tabIndex={0}
                                    role="button"
                                    aria-label={`${point.label}: ${formatNumber(point.value)}`}
                                    onMouseEnter={() => setHoverIndex(index)}
                                    onMouseLeave={() => setHoverIndex(null)}
                                    onFocus={() => setHoverIndex(index)}
                                    onBlur={() => setHoverIndex(null)}
                                />
                            </g>
                        );
                    })}

                    {tickIndices.map((index) => {
                        const anchor =
                            index === firstIndex
                                ? "start"
                                : index === lastIndex
                                  ? "end"
                                  : "middle";
                        return (
                            <text
                                key={`label-${points[index].period}`}
                                x={points[index].x}
                                y={height - 13}
                                textAnchor={anchor}
                                className="sales-chart-x-label"
                            >
                                {shortAxisLabel(index, granularity)}
                            </text>
                        );
                    })}
                </svg>

                {hoveredPoint && (
                    <div
                        className="sales-chart-tooltip"
                        style={{
                            position: "absolute",
                            left: `${(hoveredPoint.x / width) * 100}%`,
                            top: `${(hoveredPoint.y / height) * 100}%`,
                            transform: tooltipTransform,
                            pointerEvents: "none",
                        }}
                    >
                        <div className="sales-chart-tooltip-period">
                            {hoveredPoint.label}
                        </div>
                        <div className="sales-chart-tooltip-value">
                            <span className="sales-chart-tooltip-metric">
                                {METRICS[metric].label}
                            </span>
                            <span className="sales-chart-tooltip-number">
                                {formatNumber(hoveredPoint.value)}
                            </span>
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
}

export default SalesPerformanceChart;
