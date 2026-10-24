function KpiCard({ kpi }) {
    if (!kpi.available) {
        return (
            <div className="kpi-card kpi-card-unavailable">
                <div className="kpi-card-header">
                    <p className="kpi-label">{kpi.label}</p>
                    <span className="kpi-unavailable-badge">UNAVAILABLE</span>
                </div>
                <p className="kpi-value kpi-value-unavailable">Unavailable</p>
                <p className="kpi-unavailable-reason">{kpi.unavailable_reason}</p>
                <p className="kpi-period">{kpi.period_label}</p>
            </div>
        );
    }

    const hasSignal = kpi.delta_pct !== null && kpi.delta_pct !== undefined;
    const isPositive = hasSignal && kpi.delta_pct >= 0;

    return (
        <div className="kpi-card">
            <div className="kpi-card-header">
                <p className="kpi-label">{kpi.label}</p>
                {kpi.preview && <span className="kpi-preview-badge">PREVIEW</span>}
            </div>

            <p
                className="kpi-value"
                style={
                    hasSignal
                        ? { color: isPositive ? "var(--fin-up)" : "var(--fin-down)" }
                        : undefined
                }
            >
                {kpi.value}
            </p>

            {kpi.note && <p className="kpi-note">{kpi.note}</p>}
            <p className="kpi-period">{kpi.period_label}</p>
        </div>
    );
}

export default KpiCard;
