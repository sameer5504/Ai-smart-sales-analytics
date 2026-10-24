const CANCELLED_PREFIX = "C";

function isValidRow(row) {
    const orderId = (row.order_id || "").toString().trim().toUpperCase();
    return (
        row.date &&
        !orderId.startsWith(CANCELLED_PREFIX) &&
        Number(row.quantity) > 0 &&
        Number(row.unit_price) > 0
    );
}

export function cleanRows(rawRows) {
    return rawRows.filter(isValidRow).map((row) => ({
        ...row,
        date: new Date(row.date),
        quantity: Number(row.quantity),
        unit_price: Number(row.unit_price),
        revenue: Number(row.revenue ?? row.quantity * row.unit_price),
    }));
}

export function filterByDateRange(rows, startDate, endDate) {
    return rows.filter((row) => {
        if (startDate && row.date < new Date(startDate)) return false;
        if (endDate && row.date > new Date(endDate)) return false;
        return true;
    });
}

export function filterByProduct(rows, productKey) {
    if (!productKey) return rows;
    return rows.filter((row) => (row.product_id || row.product_name) === productKey);
}

export function getProductOptions(rows) {
    const map = new Map();
    rows.forEach((row) => {
        const key = row.product_id || row.product_name;
        if (!map.has(key)) {
            map.set(key, { id: key, name: row.product_name });
        }
    });
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
}

export function getDateBounds(rows) {
    if (!rows || !rows.length) return { minDate: "", maxDate: "" };

    const times = rows.map((row) => new Date(row.date).getTime());
    const toInputValue = (t) => new Date(t).toISOString().slice(0, 10);

    // Math.min(...times)/Math.max(...times) breaks on large arrays -
    // spreading thousands of arguments into a function call can exceed the
    // JS engine's call-stack argument limit ("Maximum call stack size
    // exceeded"). reduce() has no such limit.
    const minTime = times.reduce((min, t) => (t < min ? t : min), times[0]);
    const maxTime = times.reduce((max, t) => (t > max ? t : max), times[0]);

    return {
        minDate: toInputValue(minTime),
        maxDate: toInputValue(maxTime),
    };
}

function countUniqueOrders(rows) {
    const ids = rows
        .map((r) => r.order_id)
        .filter((id) => id !== null && id !== undefined);
    return new Set(ids).size;
}

function periodKey(date, granularity) {
    if (granularity === "daily") {
        return date.toISOString().slice(0, 10);
    }
    if (granularity === "weekly") {
        const d = new Date(date);
        d.setUTCDate(d.getUTCDate() - d.getUTCDay());
        return d.toISOString().slice(0, 10);
    }
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

const monthFormatter = new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "numeric",
});

function formatMonthLabel(periodKeyValue) {
    const [year, month] = periodKeyValue.split("-");
    return monthFormatter.format(new Date(Number(year), Number(month) - 1, 1));
}

function formatDMY(date) {
    const d = String(date.getUTCDate()).padStart(2, "0");
    const m = String(date.getUTCMonth() + 1).padStart(2, "0");
    const y = date.getUTCFullYear();
    return `${d}/${m}/${y}`;
}

function formatPeriodLabel(periodKeyValue, granularity) {
    if (granularity === "weekly") {
        const start = new Date(`${periodKeyValue}T00:00:00Z`);
        const end = new Date(start);
        end.setUTCDate(end.getUTCDate() + 6);
        return `${formatDMY(start)} - ${formatDMY(end)}`;
    }
    if (granularity === "daily") {
        return formatDMY(new Date(`${periodKeyValue}T00:00:00Z`));
    }
    return formatMonthLabel(periodKeyValue);
}

function granularityLabel(g) {
    if (g === "daily") return "Day-on-day";
    if (g === "weekly") return "Week-on-week";
    return "Month-on-month";
}

export function groupByPeriod(rows, granularity) {
    const groups = new Map();

    rows.forEach((row) => {
        const key = periodKey(row.date, granularity);
        if (!groups.has(key)) {
            groups.set(key, {
                period: key,
                total_revenue: 0,
                units_sold: 0,
                orderIds: new Set(),
            });
        }
        const g = groups.get(key);
        g.total_revenue += row.revenue;
        g.units_sold += row.quantity;
        if (row.order_id !== null && row.order_id !== undefined) {
            g.orderIds.add(row.order_id);
        }
    });

    return Array.from(groups.values())
        .map((g) => ({
            period: g.period,
            label: formatPeriodLabel(g.period, granularity),
            total_revenue: Math.round(g.total_revenue * 100) / 100,
            units_sold: g.units_sold,
            order_count: g.orderIds.size,
        }))
        .sort((a, b) => (a.period > b.period ? 1 : -1));
}

function formatDateRangeLabel(rows) {
    if (!rows.length) return "";
    const times = rows.map((r) => r.date.getTime());
    // Same fix as getDateBounds - reduce() instead of Math.min/max(...spread)
    // to avoid "Maximum call stack size exceeded" on large datasets.
    const minTime = times.reduce((min, t) => (t < min ? t : min), times[0]);
    const maxTime = times.reduce((max, t) => (t > max ? t : max), times[0]);
    const min = new Date(minTime);
    const max = new Date(maxTime);
    const minLabel = monthFormatter.format(min);
    const maxLabel = monthFormatter.format(max);
    return minLabel === maxLabel ? minLabel : `${minLabel} \u2013 ${maxLabel}`;
}

function formatCurrency(value, currency = null, { decimals = 0 } = {}) {
    const formatted = new Intl.NumberFormat("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(value);
    // No currency for this dataset/session - show the number on its own
    // rather than guessing or forcing a default currency onto it.
    return currency ? `${formatted} ${currency}` : formatted;
}

function formatNumber(value) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function computeGrowthCard(periodPoints, key, label, granularity) {
    if (periodPoints.length < 2) {
        return {
            label,
            value: null,
            delta_pct: null,
            period_label: "",
            available: false,
            unavailable_reason: `Need at least two ${granularity} periods of data to calculate growth.`,
        };
    }

    const current = periodPoints[periodPoints.length - 1];
    const previous = periodPoints[periodPoints.length - 2];

    const delta =
        previous[key] === 0
            ? null
            : ((current[key] - previous[key]) / previous[key]) * 100;

    return {
        label,
        value: delta !== null ? `${delta.toFixed(1)}%` : null,
        delta_pct: delta,
        period_label: `${current.label} against ${previous.label}`,
        available: delta !== null,
        unavailable_reason:
            delta === null ? "Previous period had zero to compare against." : null,
        note: `${granularityLabel(granularity)} comparison.`,
        preview: true,
    };
}

// now accepts `granularity` so Growth Rate cards react to the
// Daily/Weekly/Monthly toggle instead of always comparing months ---
export function computeKpiCards(
    filteredRows,
    granularity = "monthly",
    currency = null,
) {
    const periodLabel = formatDateRangeLabel(filteredRows);

    if (!filteredRows.length) {
        return [
            "Total Revenue",
            "Total Units Sold",
            "Number of Orders",
            "Average Order Value",
            "Revenue Growth Rate",
            "Sales Growth Rate",
        ].map((label) => ({
            label,
            value: null,
            delta_pct: null,
            period_label: "",
            available: false,
            unavailable_reason: "No data available for the selected period.",
        }));
    }

    const totalRevenue = filteredRows.reduce((sum, r) => sum + r.revenue, 0);
    const totalUnits = filteredRows.reduce((sum, r) => sum + r.quantity, 0);
    const orderCount = countUniqueOrders(filteredRows);
    const avgOrderValue = orderCount > 0 ? totalRevenue / orderCount : null;

    const periodPoints = groupByPeriod(filteredRows, granularity);
    const revenueGrowth = computeGrowthCard(
        periodPoints,
        "total_revenue",
        "Revenue Growth Rate",
        granularity,
    );
    const salesGrowth = computeGrowthCard(
        periodPoints,
        "units_sold",
        "Sales Growth Rate",
        granularity,
    );

    return [
        {
            label: "Total Revenue",
            value: formatCurrency(totalRevenue, currency),
            delta_pct: null,
            period_label: periodLabel,
            available: true,
            note: periodPoints.length < 2 ? "No earlier period in your file" : null,
        },
        {
            label: "Total Units Sold",
            value: formatNumber(totalUnits),
            delta_pct: null,
            period_label: periodLabel,
            available: true,
            note: periodPoints.length < 2 ? "No earlier period in your file" : null,
        },
        {
            label: "Number of Orders",
            value: formatNumber(orderCount),
            delta_pct: null,
            period_label: periodLabel,
            available: true,
        },
        avgOrderValue !== null
            ? {
                  // CHANGED: 2 decimals so small averages aren't rounded away
                  label: "Average Order Value",
                  value: formatCurrency(avgOrderValue, currency, { decimals: 2 }),
                  delta_pct: null,
                  period_label: periodLabel,
                  available: true,
              }
            : {
                  label: "Average Order Value",
                  value: null,
                  delta_pct: null,
                  period_label: periodLabel,
                  available: false,
                  unavailable_reason: "No orders to divide by.",
              },
        revenueGrowth,
        salesGrowth,
    ];
}

export function computeChartSeries(filteredRows, granularity) {
    return groupByPeriod(filteredRows, granularity);
}

export function computeTopProducts(filteredRows, topN = 5) {
    const map = new Map();
    filteredRows.forEach((row) => {
        const key = row.product_id || row.product_name;
        if (!map.has(key)) {
            map.set(key, {
                product_id: key,
                product_name: row.product_name,
                total_revenue: 0,
            });
        }
        map.get(key).total_revenue += row.revenue;
    });

    const sorted = Array.from(map.values()).sort(
        (a, b) => b.total_revenue - a.total_revenue,
    );

    return {
        top_products: sorted.slice(0, topN),
        bottom_products: sorted.slice(-topN).reverse(),
    };
}

export function computeProductRevenueDistribution(filteredRows, topN = 5) {
    const map = new Map();
    filteredRows.forEach((row) => {
        const key = row.product_id || row.product_name;
        if (!map.has(key)) {
            map.set(key, { name: row.product_name, value: 0 });
        }
        map.get(key).value += row.revenue;
    });

    const sorted = Array.from(map.values()).sort((a, b) => b.value - a.value);

    if (sorted.length <= topN) {
        return sorted;
    }

    const top = sorted.slice(0, topN);
    const othersValue = sorted.slice(topN).reduce((sum, p) => sum + p.value, 0);

    return [...top, { name: "Others", value: othersValue }];
}

export function computeTopProductsByMetric(filteredRows, metric, topN = 5) {
    const map = new Map();

    filteredRows.forEach((row) => {
        const key = row.product_id || row.product_name;
        if (!map.has(key)) {
            map.set(key, {
                product_id: key,
                product_name: row.product_name,
                total_revenue: 0,
                units_sold: 0,
                orderIds: new Set(),
            });
        }
        const entry = map.get(key);
        entry.total_revenue += row.revenue;
        entry.units_sold += row.quantity;
        if (row.order_id !== null && row.order_id !== undefined) {
            entry.orderIds.add(row.order_id);
        }
    });

    const list = Array.from(map.values()).map((entry) => ({
        product_id: entry.product_id,
        product_name: entry.product_name,
        value:
            metric === "units_sold"
                ? entry.units_sold
                : metric === "order_count"
                  ? entry.orderIds.size
                  : entry.total_revenue,
    }));

    const sorted = list.sort((a, b) => b.value - a.value);

    return {
        top_products: sorted.slice(0, topN),
        bottom_products: sorted.slice(-topN).reverse(),
    };
}

export function formatMetricValue(metric, value, currency = null) {
    if (metric === "total_revenue") {
        return formatCurrency(value, currency);
    }
    return formatNumber(value);
}
