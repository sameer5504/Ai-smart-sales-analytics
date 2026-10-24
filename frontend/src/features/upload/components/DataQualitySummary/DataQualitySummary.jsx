import { useState } from "react";
import "./DataQualitySummary.css";

/**
 * What preparing the uploaded file did to it (US-1.6.2).
 *
 * The headline carries the result, the bar carries the proportion, and the
 * rows carry the counts. Nothing is stated twice: the bar is aria-hidden
 * because the headline already says the same thing in words, and a group
 * shows its total only when it has more than one row under it.
 *
 * Tone tracks how much of the file survived, so a file that lost a third of
 * its rows does not get the same green as a clean one.
 *
 * Removals and corrections stay in separate groups because one keeps the row
 * and one does not. Merging them into a single "problems" count makes an
 * ordinary file look broken.
 *
 * The handling rules never change between uploads, so they sit behind a
 * disclosure instead of on screen every time.
 *
 * A file that could not be read, and one whose columns could not be matched,
 * are dead ends rather than results. Both drop the counts and say what to do.
 */

const FIELD_LABELS = {
    transaction_date: "Date",
    order_id: "Order number",
    product_id: "Product ID",
    product_name: "Product name",
    quantity: "Quantity",
    unit_price: "Unit price",
};

function DataQualitySummary({ data, validation }) {
    if (!data) return null;

    if (validation && validation.is_valid === false) {
        return <UnmatchedColumns fields={validation.missing_required_fields} />;
    }

    const {
        rows_read: rowsRead,
        rows_kept: rowsKept,
        values_filled: valuesFilled,
        rows_excluded: rowsExcluded,
        duplicates_removed: duplicatesRemoved,
        flagged_missing: flaggedMissing = {},
    } = data;

    if (!rowsRead) return <UnreadableFile />;

    const rowsRemoved = rowsExcluded + duplicatesRemoved;
    const missingOrderIds = flaggedMissing.order_id || 0;
    const keptPercent = Math.round((rowsKept / rowsRead) * 100);
    const tone = keptPercent >= 95 ? "good" : keptPercent >= 80 ? "fair" : "poor";

    const removed = [
        duplicatesRemoved > 0 && {
            key: "dupes",
            label: "Duplicates",
            count: duplicatesRemoved,
        },
        rowsExcluded > 0 && {
            key: "incomplete",
            label: "Missing required fields",
            count: rowsExcluded,
        },
    ].filter(Boolean);

    const filled =
        valuesFilled > 0
            ? [{ key: "blanks", label: "Blank optional values", count: valuesFilled }]
            : [];

    return (
        <section className={`dq dq-${tone}`} aria-label="Data quality summary">
            <header className="dq-head">
                <span className="dq-dot" aria-hidden="true" />
                <h3 className="dq-headline">
                    {rowsKept.toLocaleString()} of {rowsRead.toLocaleString()} rows
                    ready
                </h3>
                <span className="dq-percent">{keptPercent}%</span>
            </header>

            <div className="dq-bar" aria-hidden="true">
                <span className="dq-bar-fill" style={{ width: `${keptPercent}%` }} />
            </div>

            {removed.length === 0 && filled.length === 0 && (
                <p className="dq-clear">Nothing removed or filled.</p>
            )}

            <Group title="Removed" total={rowsRemoved} items={removed} />
            <Group title="Filled in" total={valuesFilled} items={filled} />

            {missingOrderIds > 0 && (
                <p className="dq-note">
                    <strong>{missingOrderIds.toLocaleString()}</strong>{" "}
                    {missingOrderIds === 1 ? "row has" : "rows have"} no order number.
                    Counted in revenue, not in order count.
                </p>
            )}

            <Disclosure summary="How rows are handled">
                Rows need a date, product, quantity and price. Optional gaps get a
                default. Exact duplicates collapse into one.
            </Disclosure>
        </section>
    );
}

function UnmatchedColumns({ fields = [] }) {
    return (
        <section className="dq dq-blocked" aria-label="Data quality summary">
            <header className="dq-head">
                <span className="dq-dot" aria-hidden="true" />
                <h3 className="dq-headline">Some columns were not matched</h3>
            </header>

            <ul className="dq-chips">
                {fields.map((field) => (
                    <li className="dq-chip" key={field}>
                        {FIELD_LABELS[field] || field}
                    </li>
                ))}
            </ul>

            <p className="dq-note">
                Nothing was saved. Rename these columns to match the template and upload
                again.
            </p>
        </section>
    );
}

function UnreadableFile() {
    return (
        <section className="dq dq-blocked" aria-label="Data quality summary">
            <header className="dq-head">
                <span className="dq-dot" aria-hidden="true" />
                <h3 className="dq-headline">No rows could be read</h3>
            </header>

            <p className="dq-note">
                The file may be empty or saved in a format we cannot open. Check it and
                upload again.
            </p>
        </section>
    );
}

function Group({ title, total, items }) {
    if (items.length === 0) return null;

    return (
        <div className="dq-group">
            <div className="dq-group-head">
                <h4 className="dq-group-title">{title}</h4>
                {items.length > 1 && (
                    <span className="dq-group-total">{total.toLocaleString()}</span>
                )}
            </div>
            <ul className="dq-rows">
                {items.map((item) => (
                    <li className="dq-row" key={item.key}>
                        <span className="dq-row-label">{item.label}</span>
                        <span className="dq-row-count">
                            {item.count.toLocaleString()}
                        </span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function Disclosure({ summary, children }) {
    const [open, setOpen] = useState(false);

    return (
        <div className="dq-disclosure">
            <button
                type="button"
                className="dq-disclosure-toggle"
                aria-expanded={open}
                onClick={() => setOpen((wasOpen) => !wasOpen)}
            >
                <span
                    className={open ? "dq-caret dq-caret-open" : "dq-caret"}
                    aria-hidden="true"
                >
                    &rsaquo;
                </span>
                {summary}
            </button>
            {open && <p className="dq-disclosure-body">{children}</p>}
        </div>
    );
}

export default DataQualitySummary;
