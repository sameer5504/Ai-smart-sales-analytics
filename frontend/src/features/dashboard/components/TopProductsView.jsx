import { useEffect, useState } from "react";
import { formatMetricValue } from "../utils/aggregateDashboardData";

const METRIC_LABELS = {
    total_revenue: "revenue",
    units_sold: "units sold",
    order_count: "orders",
};

function ProductRow({ product, max, rank, metric, variant, currency }) {
    const target = max > 0 ? (product.value / max) * 100 : 0;
    const [width, setWidth] = useState(0);

    useEffect(() => {
        const id = requestAnimationFrame(() => setWidth(target));
        return () => cancelAnimationFrame(id);
    }, [target]);

    return (
        <div className="top-product-row">
            <span className={`top-product-rank top-product-rank-${variant}`}>
                {rank}
            </span>
            <span className="top-product-name" title={product.product_name}>
                {product.product_name}
            </span>
            <div className="top-product-bar-track">
                <div
                    className={`top-product-bar-fill top-product-bar-fill-${variant}`}
                    style={{ width: `${width}%` }}
                />
            </div>
            <span className="top-product-value">
                {formatMetricValue(metric, product.value, currency)}
            </span>
        </div>
    );
}

function TopProductsView({ data, metric = "total_revenue", currency }) {
    const { top_products: topProducts, bottom_products: bottomProducts } = data;

    if (!topProducts.length) {
        return (
            <div className="top-products-card top-products-unavailable">
                <p className="chart-title">Top / Bottom products</p>
                <p className="kpi-unavailable-reason">
                    No data available for this period.
                </p>
            </div>
        );
    }

    const allValues = [...topProducts, ...bottomProducts].map((p) => p.value);
    const max = Math.max(...allValues, 1);
    const metricLabel = METRIC_LABELS[metric] || "revenue";

    return (
        <div className="top-products-card">
            <p className="chart-title">Top products — by {metricLabel}</p>
            {topProducts.map((product, index) => (
                <ProductRow
                    key={product.product_id}
                    product={product}
                    max={max}
                    rank={index + 1}
                    metric={metric}
                    variant="top"
                    currency={currency}
                />
            ))}

            <p className="chart-title top-products-bottom-title">Lowest-selling</p>
            {bottomProducts.map((product, index) => (
                <ProductRow
                    key={product.product_id}
                    product={product}
                    max={max}
                    rank={index + 1}
                    metric={metric}
                    variant="bottom"
                    currency={currency}
                />
            ))}
        </div>
    );
}

export default TopProductsView;
