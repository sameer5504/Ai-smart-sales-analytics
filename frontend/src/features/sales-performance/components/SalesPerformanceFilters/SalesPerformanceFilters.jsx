import "./SalesPerformanceFilters.css";

function SalesPerformanceFilters({
    granularity,
    onGranularityChange,
    startDate,
    onStartDateChange,
    endDate,
    onEndDateChange,
    minDate,
    maxDate,
    productOptions = [],
    selectedProduct = "",
    onProductChange,
    disabled = false,
}) {
    const granularities = [
        { value: "daily", label: "Daily" },
        { value: "weekly", label: "Weekly" },
        { value: "monthly", label: "Monthly" },
    ];

    // Start date can't go earlier than the file's min date, or later than
    // the currently selected end date (or the file's max date if no end set).
    const startMin = minDate || undefined;
    const startMax = endDate || maxDate || undefined;

    // End date can't go earlier than the currently selected start date (or
    // the file's min date if no start set), or later than the file's max date.
    const endMin = startDate || minDate || undefined;
    const endMax = maxDate || undefined;

    return (
        <div className="sales-performance-filters">
            <div className="sales-filter-group">
                <span className="sales-filter-label">Granularity</span>

                <div
                    className="sales-granularity-control"
                    role="group"
                    aria-label="Time granularity"
                >
                    {granularities.map((option) => {
                        const isActive = granularity === option.value;

                        return (
                            <button
                                key={option.value}
                                type="button"
                                className={`sales-granularity-button ${
                                    isActive ? "sales-granularity-button-active" : ""
                                }`}
                                onClick={() => onGranularityChange(option.value)}
                                disabled={disabled}
                                aria-pressed={isActive}
                            >
                                {option.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            <div className="sales-filter-group">
                <label className="sales-filter-label" htmlFor="sales-start-date">
                    Start Date
                </label>

                <input
                    id="sales-start-date"
                    className="sales-date-input"
                    type="date"
                    value={startDate}
                    min={startMin}
                    max={startMax}
                    onChange={(event) => onStartDateChange(event.target.value)}
                    disabled={disabled}
                />
            </div>

            <div className="sales-filter-group">
                <label className="sales-filter-label" htmlFor="sales-end-date">
                    End Date
                </label>

                <input
                    id="sales-end-date"
                    className="sales-date-input"
                    type="date"
                    value={endDate}
                    min={endMin}
                    max={endMax}
                    onChange={(event) => onEndDateChange(event.target.value)}
                    disabled={disabled}
                />
            </div>

            <div className="sales-filter-group">
                <label className="sales-filter-label" htmlFor="sales-product-filter">
                    Item
                </label>

                <select
                    id="sales-product-filter"
                    className="sales-date-input"
                    value={selectedProduct}
                    onChange={(event) => onProductChange?.(event.target.value)}
                    disabled={disabled || !productOptions.length}
                >
                    <option value="">All products</option>
                    {productOptions.map((product) => (
                        <option key={product.id} value={product.id}>
                            {product.name}
                        </option>
                    ))}
                </select>
            </div>
        </div>
    );
}

export default SalesPerformanceFilters;
