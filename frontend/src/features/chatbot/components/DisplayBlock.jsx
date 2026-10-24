import {
    BarChart,
    Bar,
    LineChart,
    Line,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    CartesianGrid,
    Cell,
} from "recharts";

const PALETTE = [
    "#4F46E5",
    "#059669",
    "#D97706",
    "#DC2626",
    "#7C3AED",
    "#0891B2",
    "#DB2777",
    "#65A30D",
];

function colorFor(label) {
    let hash = 0;
    for (let i = 0; i < label.length; i++) {
        hash = label.charCodeAt(i) + ((hash << 5) - hash);
    }
    return PALETTE[Math.abs(hash) % PALETTE.length];
}

function formatValue(value, unit) {
    const formatted = Number(value).toLocaleString();
    return unit === "units" ? formatted : `${formatted} ${unit}`;
}

export default function DisplayBlock({ display }) {
    if (!display) return null;

    if (display.type === "insufficient_data") {
        return (
            <div className="chatbot__display chatbot__display--insufficient">
                <span className="chatbot__badge chatbot__badge--muted">
                    NOT ENOUGH DATA
                </span>
                <p className="chatbot__display-reason" dir="auto">
                    {display.reason}
                </p>
            </div>
        );
    }

    if (display.type === "metric_change") {
        const isUp = display.change_pct >= 0;
        const arrow = isUp ? "\u25B2" : "\u25BC";
        const trendClass = isUp ? "chatbot__trend--up" : "chatbot__trend--down";
        const hasPeriods = display.previous_period && display.current_period;

        return (
            <div className="chatbot__display chatbot__metric-change">
                <p className="chatbot__display-title" dir="auto">
                    {display.label}
                </p>
                <div className="chatbot__metric-row">
                    <span className="chatbot__metric-value">
                        {formatValue(display.current_value, display.unit)}
                    </span>
                    <span className={`chatbot__trend ${trendClass}`}>
                        <span aria-hidden="true">{arrow}</span>
                        {Math.abs(display.change_pct)}%
                    </span>
                </div>
                {hasPeriods && (
                    <p className="chatbot__metric-sub" dir="auto">
                        {display.previous_period} (
                        {formatValue(display.previous_value, display.unit)}){" \u2192 "}
                        {display.current_period} (
                        {formatValue(display.current_value, display.unit)})
                    </p>
                )}
            </div>
        );
    }

    if (display.type === "table") {
        return (
            <div className="chatbot__display">
                <p className="chatbot__display-title" dir="auto">
                    {display.title}
                </p>

                <div className="chatbot__table-wrap">
                    <table className="chatbot__table">
                        <thead>
                            <tr>
                                {display.columns.map((c) => (
                                    <th key={c}>{c}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {display.rows.map((row, i) => (
                                <tr key={i}>
                                    {row.map((cell, j) => (
                                        <td key={j}>{cell}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    }

    if (display.type === "chart") {
        const chartData = display.labels.map((label, i) => {
            const point = { name: label };
            display.series.forEach((s) => (point[s.name] = s.values[i]));
            return point;
        });

        return (
            <div className="chatbot__display">
                <p className="chatbot__display-title" dir="auto">
                    {display.title}
                </p>
                {display.series.map((s) => (
                    <div className="chatbot__chart-panel" key={s.name}>
                        <p className="chatbot__chart-panel-label">{s.name}</p>
                        <ResponsiveContainer width="100%" height={140}>
                            {display.chart_kind === "bar" ? (
                                <BarChart data={chartData}>
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        vertical={false}
                                    />
                                    <XAxis dataKey="name" fontSize={11} />
                                    <YAxis fontSize={11} width={36} />
                                    <Tooltip />
                                    <Bar dataKey={s.name} radius={[3, 3, 0, 0]}>
                                        {chartData.map((entry, i) => (
                                            <Cell key={i} fill={colorFor(entry.name)} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            ) : (
                                <LineChart data={chartData}>
                                    <CartesianGrid
                                        strokeDasharray="3 3"
                                        vertical={false}
                                    />
                                    <XAxis dataKey="name" fontSize={11} />
                                    <YAxis fontSize={11} width={36} />
                                    <Tooltip />
                                    <Line
                                        type="monotone"
                                        dataKey={s.name}
                                        stroke="var(--primary-600, #17607a)"
                                        strokeWidth={2}
                                        dot={{ r: 3 }}
                                    />
                                </LineChart>
                            )}
                        </ResponsiveContainer>
                    </div>
                ))}
            </div>
        );
    }

    return null;
}
