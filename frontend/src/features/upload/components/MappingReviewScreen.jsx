import { useEffect, useRef } from "react";
import FieldDropdown from "./FieldDropdown.jsx";
import DataQualitySummary from "./DataQualitySummary/DataQualitySummary.jsx";
import { useMapping } from "../hooks/useMapping.js";

function labelForField(schema, key) {
    return schema.find((field) => field.key === key)?.label || key;
}

// Disabled buttons get the design spec's flattened n-100/n-400 treatment;
// inline styles don't respond to the `disabled` attribute on their own.
function buttonStyle(base, disabled) {
    if (!disabled) return base;
    return {
        ...base,
        background: "var(--n-100)",
        border: "1px solid transparent",
        color: "var(--n-400)",
        cursor: "not-allowed",
    };
}

// Small pill used both in the per-row badges and the top-of-card legend.
function Badge({ tone = "neutral", children }) {
    const tones = {
        critical: {
            bg: "var(--critical-bg)",
            color: "var(--critical)",
            border: "var(--critical-border)",
        },
        neutral: { bg: "var(--n-50)", color: "var(--n-500)", border: "var(--n-100)" },
        success: {
            bg: "var(--success-bg)",
            color: "var(--success)",
            border: "var(--success-border)",
        },
    };
    const t = tones[tone] || tones.neutral;
    return (
        <span
            style={{
                display: "inline-flex",
                alignItems: "center",
                height: "19px",
                padding: "0 7px",
                borderRadius: "var(--r-sm)",
                background: t.bg,
                color: t.color,
                border: `1px solid ${t.border}`,
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                fontWeight: 500,
                letterSpacing: ".03em",
                textTransform: "uppercase",
                whiteSpace: "nowrap",
            }}
        >
            {children}
        </span>
    );
}

function Banner({ tone, title, children }) {
    const tones = {
        critical: {
            bg: "var(--critical-surface)",
            border: "var(--critical-border)",
            accent: "var(--critical)",
        },
        success: {
            bg: "var(--success-bg)",
            border: "var(--success-border)",
            accent: "var(--success)",
        },
    };
    const t = tones[tone] || tones.critical;
    const role = tone === "success" ? "status" : "alert";
    return (
        <div
            role={role}
            style={{
                display: "flex",
                gap: "12px",
                alignItems: "flex-start",
                border: `1px solid ${t.border}`,
                borderInlineStart: `4px solid ${t.accent}`,
                borderRadius: "var(--r-md)",
                background: t.bg,
                padding: "14px 16px",
                marginBottom: "14px",
            }}
        >
            <span
                aria-hidden="true"
                style={{
                    color: t.accent,
                    fontFamily: "var(--font-sans)",
                    fontWeight: 600,
                    fontSize: "14px",
                    lineHeight: 1.5,
                }}
            >
                {tone === "success" ? "✓" : "✕"}
            </span>
            <div>
                {title && (
                    <div
                        style={{
                            fontFamily: "var(--font-sans)",
                            fontWeight: 600,
                            fontSize: "13.5px",
                            color: t.accent,
                            marginBottom: "3px",
                        }}
                    >
                        {title}
                    </div>
                )}
                <div
                    style={{
                        fontFamily: "var(--font-sans)",
                        fontSize: "13px",
                        lineHeight: 1.6,
                        color: "var(--n-700)",
                    }}
                >
                    {children}
                </div>
            </div>
        </div>
    );
}

// Confirmation modal shown before destructive actions (e.g. resetting the
// mapping). Rendered as a fixed overlay so it doesn't disturb the layout of
// the action bar underneath it.
function ConfirmDialog({ title, message, onConfirm, onCancel, confirmDisabled }) {
    return (
        <div
            role="presentation"
            onClick={onCancel}
            style={{
                position: "fixed",
                inset: 0,
                background: "rgba(15, 23, 42, 0.45)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1000,
                padding: "16px",
            }}
        >
            <div
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-dialog-title"
                onClick={(e) => e.stopPropagation()}
                style={{
                    background: "var(--n-0)",
                    borderRadius: "var(--r-lg)",
                    boxShadow: "var(--e2, 0 12px 32px rgba(0,0,0,.18))",
                    padding: "24px",
                    maxWidth: "380px",
                    width: "100%",
                }}
            >
                <h2
                    id="confirm-dialog-title"
                    style={{
                        margin: "0 0 8px",
                        fontFamily: "var(--font-sans)",
                        fontWeight: 600,
                        fontSize: "17px",
                        color: "var(--n-800)",
                    }}
                >
                    {title}
                </h2>
                <p
                    style={{
                        margin: "0 0 20px",
                        fontFamily: "var(--font-sans)",
                        fontSize: "14px",
                        lineHeight: 1.5,
                        color: "var(--n-600)",
                    }}
                >
                    {message}
                </p>
                <div
                    style={{
                        display: "flex",
                        justifyContent: "flex-end",
                        gap: "8px",
                    }}
                >
                    <button
                        type="button"
                        onClick={onCancel}
                        style={styles.secondaryButton}
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={onConfirm}
                        disabled={confirmDisabled}
                        style={buttonStyle(styles.submitButton, confirmDisabled)}
                    >
                        Yes, reset
                    </button>
                </div>
            </div>
        </div>
    );
}

function MappingReviewScreen({ filename, dataType, initialColumns, currency } = {}) {
    const {
        schema,
        schemaError,
        phase,
        columnsText,
        setColumnsText,
        columns,
        mapping,
        detecting,
        detectError,
        submitState,
        submitErrors,
        submitErrorMessage,
        uploadResult,
        isFinishingUpload,
        summary,
        confirmingReset,
        handleDetect,
        handleMappingChange,
        handleStartOver,
        handleCancelReset,
        handleSubmit,
        handleContinue,
    } = useMapping({ filename, dataType, initialColumns, currency });

    // Submitting happens from the bottom of the page (the button lives at
    // the end of the card), but the error banner renders near the top -
    // without this, a failed submit (e.g. the duplicate-upload warning)
    // is invisible unless the user manually scrolls up to see it.
    const submitErrorRef = useRef(null);
    useEffect(() => {
        if ((submitErrors || submitErrorMessage) && submitErrorRef.current) {
            submitErrorRef.current.scrollIntoView?.({
                behavior: "smooth",
                block: "center",
            });
        }
    }, [submitErrors, submitErrorMessage]);

    if (schemaError) {
        return (
            <div style={styles.page}>
                <Banner tone="critical" title="Could not load the standard field list">
                    {schemaError}
                </Banner>
            </div>
        );
    }

    if (!schema) {
        return (
            <div style={styles.page}>
                <p style={styles.body}>Loading standard fields…</p>
            </div>
        );
    }

    if (phase === "loading") {
        return (
            <div style={styles.page}>
                <div style={styles.overline}>Manual column mapping</div>
                <h1 style={styles.h1}>Column mapping</h1>
                {detectError ? (
                    <Banner
                        tone="critical"
                        title="Could not prepare the mapping review"
                    >
                        {detectError}
                    </Banner>
                ) : (
                    <p style={styles.bodyLg}>Loading the columns from your file…</p>
                )}
            </div>
        );
    }

    if (phase === "input") {
        return (
            <div style={styles.page}>
                <div style={styles.overline}>Manual column mapping</div>
                <h1 style={styles.h1}>Column mapping</h1>
                <p style={styles.bodyLg}>
                    Enter the column headers detected in your file (comma or newline
                    separated).
                </p>

                <div style={styles.card}>
                    <label htmlFor="columns-input" style={styles.label}>
                        Detected columns
                    </label>
                    <textarea
                        id="columns-input"
                        aria-label="Detected columns"
                        value={columnsText}
                        onChange={(event) => setColumnsText(event.target.value)}
                        rows={4}
                        style={styles.textarea}
                    />
                    {detectError && <Banner tone="critical">{detectError}</Banner>}
                    <button
                        type="button"
                        onClick={handleDetect}
                        disabled={detecting}
                        style={buttonStyle(styles.primaryButton, detecting)}
                    >
                        {detecting ? "Detecting…" : "Detect Mapping"}
                    </button>
                </div>
            </div>
        );
    }

    const isSubmitting = submitState === "submitting";
    const isSuccess = submitState === "success";
    const hasMissingRequired = summary.missingRequired.length > 0;
    const canSubmit = !isSubmitting && !isSuccess && !hasMissingRequired;
    const showBlockedReason = hasMissingRequired && !isSubmitting && !isSuccess;

    return (
        <div style={styles.page}>
            <div style={styles.overline}>Manual column mapping</div>
            <h1 style={styles.h1}>Review column mapping</h1>
            <p style={styles.bodyLg}>
                Your columns are on the left. Change anything we got wrong.
            </p>

            {hasMissingRequired && !isSuccess && (
                <Banner tone="critical" title="Some required fields aren't mapped yet">
                    Missing required fields:{" "}
                    {summary.missingRequired
                        .map((key) => labelForField(schema, key))
                        .join(", ")}
                </Banner>
            )}

            <div ref={submitErrorRef}>
                {submitErrors && (
                    <Banner tone="critical" title="Could not submit mapping">
                        <ul style={styles.errorList}>
                            {submitErrors.missing_required_fields?.length > 0 && (
                                <li>
                                    Missing required fields:{" "}
                                    {submitErrors.missing_required_fields
                                        .map((key) => labelForField(schema, key))
                                        .join(", ")}
                                </li>
                            )}
                            {submitErrors.duplicate_field_mapping &&
                                Object.entries(
                                    submitErrors.duplicate_field_mapping,
                                ).map(([field, cols]) => (
                                    <li key={field}>
                                        {labelForField(schema, field)} is mapped from
                                        more than one column: {cols.join(", ")}
                                    </li>
                                ))}
                            {submitErrors.unknown_fields?.length > 0 && (
                                <li>
                                    Unknown standard field(s):{" "}
                                    {submitErrors.unknown_fields.join(", ")}
                                </li>
                            )}
                            {submitErrors.unknown_columns?.length > 0 && (
                                <li>
                                    Unknown column(s):{" "}
                                    {submitErrors.unknown_columns.join(", ")}
                                </li>
                            )}
                        </ul>
                    </Banner>
                )}

                {submitErrorMessage && (
                    <Banner tone="critical" title="Couldn't submit">
                        {submitErrorMessage}
                    </Banner>
                )}
            </div>

            {isSuccess && isFinishingUpload && (
                <Banner tone="success" title="File processed successfully.">
                    {uploadResult?.row_count ?? 0} row
                    {uploadResult?.row_count === 1 ? "" : "s"} were saved using your
                    column mapping.
                </Banner>
            )}

            {/* What the confirmed mapping produced. Shown here rather than on
                the upload page because the rows are only cleaned and kept once
                a mapping has actually been applied. */}
            {isSuccess && isFinishingUpload && uploadResult?.data_quality && (
                <DataQualitySummary
                    data={uploadResult.data_quality}
                    validation={uploadResult.validation}
                />
            )}

            {isSuccess && !isFinishingUpload && (
                <Banner tone="success" title="Mapping submitted successfully.">
                    Your column mapping has been saved.
                </Banner>
            )}

            <div style={styles.card}>
                <div style={styles.cardHeaderRow}>
                    <div>
                        <h2 style={styles.h3}>Does this look right?</h2>
                        <p style={styles.cardSubtitle}>
                            Fields marked{" "}
                            <span style={{ color: "var(--critical)" }}>*</span> are
                            required.
                        </p>
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        <span style={styles.legendItem}>
                            <Badge tone="critical">Required</Badge> analysis needs it
                        </span>
                        <span style={styles.legendItem}>
                            <Badge tone="neutral">Optional</Badge> nice to have
                        </span>
                    </div>
                </div>

                <div style={styles.tableHeaderRow}>
                    <div style={styles.colHeader}>Your column</div>
                    <div />
                    <div style={styles.colHeader}>We&rsquo;ll treat it as</div>
                </div>

                {columns.map((column) => {
                    const field = mapping[column] ?? null;
                    const isDuplicate =
                        field && summary.duplicateFields[field]?.length > 1;
                    const isUnmapped = !field;
                    const fieldMeta = field
                        ? schema.find((f) => f.key === field)
                        : null;

                    return (
                        <div key={column} style={styles.row}>
                            <div>
                                <label
                                    htmlFor={`field-${column}`}
                                    style={styles.columnName}
                                >
                                    {column}
                                </label>
                            </div>
                            <div aria-hidden="true" style={styles.arrow}>
                                →
                            </div>
                            <div>
                                <FieldDropdown
                                    id={`field-${column}`}
                                    value={field}
                                    options={schema}
                                    disabled={isSubmitting || isSuccess}
                                    hasError={Boolean(isDuplicate)}
                                    onChange={(newField) =>
                                        handleMappingChange(column, newField)
                                    }
                                />
                                <div style={styles.rowMeta}>
                                    {isUnmapped && (
                                        <Badge tone="neutral">Unmapped</Badge>
                                    )}
                                    {!isUnmapped && fieldMeta?.required && (
                                        <Badge tone="critical">Required</Badge>
                                    )}
                                    {!isUnmapped &&
                                        fieldMeta &&
                                        !fieldMeta.required && (
                                            <Badge tone="neutral">Optional</Badge>
                                        )}
                                    {isDuplicate && (
                                        <span style={styles.inlineError}>
                                            Also mapped from{" "}
                                            {summary.duplicateFields[field]
                                                .filter((c) => c !== column)
                                                .join(", ")}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}

                <div style={styles.summaryPanel}>
                    <div style={styles.overlineSmall}>
                        What we still need ·{" "}
                        {schema.length - summary.missingRequired.length} of{" "}
                        {schema.length} standard fields filled
                    </div>
                    <div style={styles.summaryGrid}>
                        {schema.map((field) => {
                            const mappedColumns = summary.fieldToColumns[field.key];
                            const isMapped = Boolean(mappedColumns?.length);
                            const isMissingRequired = field.required && !isMapped;
                            const tone = isMissingRequired
                                ? "critical"
                                : isMapped
                                  ? "success"
                                  : "neutral";
                            const bg =
                                tone === "critical"
                                    ? "var(--critical-surface)"
                                    : "var(--n-0)";
                            const border =
                                tone === "critical"
                                    ? "var(--critical-border)"
                                    : "var(--n-100)";
                            return (
                                <div
                                    key={field.key}
                                    style={{
                                        ...styles.summaryItem,
                                        background: bg,
                                        borderColor: border,
                                    }}
                                >
                                    <span
                                        style={{
                                            ...styles.summaryIcon,
                                            color: isMapped
                                                ? "var(--success)"
                                                : isMissingRequired
                                                  ? "var(--critical)"
                                                  : "var(--n-400)",
                                        }}
                                    >
                                        {isMapped ? "✓" : isMissingRequired ? "✕" : "—"}
                                    </span>
                                    <span style={styles.summaryFieldName}>
                                        {field.key}
                                    </span>
                                    <span
                                        style={{
                                            ...styles.summaryStatus,
                                            color: isMissingRequired
                                                ? "var(--critical)"
                                                : "var(--n-500)",
                                        }}
                                    >
                                        {isMapped
                                            ? mappedColumns.join(", ")
                                            : isMissingRequired
                                              ? "not mapped"
                                              : "optional, not mapped"}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div style={styles.actionBar}>
                    <button
                        type="button"
                        onClick={handleStartOver}
                        disabled={isSubmitting}
                        style={buttonStyle(styles.secondaryButton, isSubmitting)}
                    >
                        Start Over
                    </button>
                    <div
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "14px",
                            flexWrap: "wrap",
                        }}
                    >
                        {showBlockedReason && (
                            <span style={styles.blockedReason}>
                                <span aria-hidden="true">✕</span> Map required fields to
                                continue.
                            </span>
                        )}
                        {isSuccess && isFinishingUpload ? (
                            <button
                                type="button"
                                onClick={handleContinue}
                                style={styles.submitButton}
                            >
                                Go to your dashboard
                            </button>
                        ) : (
                            <button
                                type="button"
                                onClick={handleSubmit}
                                disabled={!canSubmit}
                                style={buttonStyle(
                                    styles.submitButton,
                                    showBlockedReason,
                                )}
                            >
                                {isSubmitting
                                    ? "Submitting…"
                                    : isSuccess
                                      ? "Submitted"
                                      : "Submit Mapping"}
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {confirmingReset && (
                <ConfirmDialog
                    title="Reset to suggested mapping?"
                    message="This will discard any manual changes you made and restore the originally suggested column mapping."
                    onCancel={handleCancelReset}
                    onConfirm={handleStartOver}
                    confirmDisabled={isSubmitting}
                />
            )}
        </div>
    );
}

const styles = {
    page: {
        maxWidth: "880px",
        margin: "0 auto",
        padding: "48px 24px 100px",
        fontFamily: "var(--font-sans)",
        color: "var(--n-800)",
    },
    overline: {
        fontFamily: "var(--font-mono)",
        fontSize: "11.5px",
        fontWeight: 500,
        letterSpacing: ".06em",
        textTransform: "uppercase",
        color: "var(--n-400)",
        marginBottom: "10px",
    },
    overlineSmall: {
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        fontWeight: 500,
        letterSpacing: ".05em",
        textTransform: "uppercase",
        color: "var(--n-400)",
        marginBottom: "12px",
    },
    h1: {
        margin: "0 0 8px",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: "32px",
        lineHeight: 1.2,
        letterSpacing: "-.018em",
        color: "var(--n-800)",
    },
    h3: {
        margin: "0 0 4px",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: "20px",
        lineHeight: 1.35,
        letterSpacing: "-.01em",
        color: "var(--n-800)",
    },
    bodyLg: {
        margin: "0 0 24px",
        fontFamily: "var(--font-sans)",
        fontSize: "17px",
        lineHeight: 1.6,
        color: "var(--n-600)",
        maxWidth: "68ch",
    },
    body: {
        fontFamily: "var(--font-sans)",
        fontSize: "15px",
        color: "var(--n-700)",
    },
    cardSubtitle: {
        margin: 0,
        fontFamily: "var(--font-sans)",
        fontSize: "13.5px",
        color: "var(--n-500)",
    },
    card: {
        background: "var(--n-0)",
        border: "1px solid var(--n-100)",
        borderRadius: "var(--r-lg)",
        boxShadow: "var(--e1)",
        padding: "22px",
    },
    cardHeaderRow: {
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "16px",
        flexWrap: "wrap",
        paddingBottom: "16px",
        marginBottom: "8px",
        borderBottom: "1px solid var(--n-50)",
    },
    legendItem: {
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontFamily: "var(--font-sans)",
        fontSize: "12px",
        color: "var(--n-600)",
    },
    label: {
        display: "block",
        fontFamily: "var(--font-sans)",
        fontWeight: 500,
        fontSize: "13px",
        color: "var(--n-700)",
        marginBottom: "6px",
    },
    textarea: {
        width: "100%",
        fontFamily: "var(--font-sans)",
        fontSize: "14px",
        padding: "10px 12px",
        marginBottom: "14px",
        border: "1px solid var(--n-300)",
        borderRadius: "var(--r-md)",
        color: "var(--n-800)",
        resize: "vertical",
    },
    tableHeaderRow: {
        display: "grid",
        gridTemplateColumns: "1.3fr 24px 1.4fr",
        gap: "0 14px",
        padding: "0 0 8px",
        borderBottom: "1px solid var(--n-100)",
    },
    colHeader: {
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        fontWeight: 500,
        letterSpacing: ".05em",
        textTransform: "uppercase",
        color: "var(--n-400)",
    },
    row: {
        display: "grid",
        gridTemplateColumns: "1.3fr 24px 1.4fr",
        gap: "0 14px",
        alignItems: "center",
        padding: "14px 0",
        borderBottom: "1px solid var(--n-50)",
    },
    columnName: {
        fontFamily: "var(--font-mono)",
        fontWeight: 500,
        fontSize: "14.5px",
        color: "var(--n-800)",
    },
    arrow: {
        fontFamily: "var(--font-mono)",
        fontSize: "12px",
        color: "var(--n-300)",
        textAlign: "center",
    },
    rowMeta: {
        display: "flex",
        gap: "6px",
        alignItems: "center",
        marginTop: "5px",
        flexWrap: "wrap",
    },
    inlineError: {
        fontFamily: "var(--font-sans)",
        color: "var(--critical)",
        fontSize: "12px",
    },
    summaryPanel: {
        borderTop: "1px solid var(--n-100)",
        marginTop: "8px",
        paddingTop: "18px",
    },
    summaryGrid: {
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: "8px 16px",
    },
    summaryItem: {
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "8px 10px",
        borderRadius: "var(--r-md)",
        border: "1px solid var(--n-100)",
    },
    summaryIcon: {
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: "12px",
        width: "14px",
        flex: "none",
    },
    summaryFieldName: {
        fontFamily: "var(--font-mono)",
        fontWeight: 500,
        fontSize: "13px",
        flex: 1,
        color: "var(--n-800)",
    },
    summaryStatus: {
        fontFamily: "var(--font-mono)",
        fontSize: "12px",
    },
    actionBar: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        flexWrap: "wrap",
        marginTop: "22px",
        paddingTop: "18px",
        borderTop: "1px solid var(--n-100)",
    },
    blockedReason: {
        display: "flex",
        gap: "6px",
        alignItems: "center",
        fontFamily: "var(--font-sans)",
        fontSize: "12.5px",
        color: "var(--critical)",
    },
    errorList: {
        margin: "6px 0 0",
        paddingLeft: "20px",
    },
    primaryButton: {
        height: "var(--ctl-md)",
        padding: "0 16px",
        border: "1px solid transparent",
        borderRadius: "var(--r-md)",
        background: "var(--primary-600)",
        color: "var(--n-0)",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: "15px",
        cursor: "pointer",
    },
    secondaryButton: {
        height: "var(--ctl-md)",
        padding: "0 16px",
        border: "1px solid var(--n-300)",
        borderRadius: "var(--r-md)",
        background: "var(--n-0)",
        color: "var(--n-700)",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: "14px",
        cursor: "pointer",
    },
    submitButton: {
        height: "44px",
        padding: "0 18px",
        border: "1px solid transparent",
        borderRadius: "var(--r-md)",
        background: "var(--primary-600)",
        color: "var(--n-0)",
        fontFamily: "var(--font-sans)",
        fontWeight: 600,
        fontSize: "15px",
        cursor: "pointer",
    },
};

export default MappingReviewScreen;
