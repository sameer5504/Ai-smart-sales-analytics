import { useState } from "react";

// Reusable dropdown for picking which standard field a source column maps
// to. Used by the mapping review screen, one instance per source column.
// Visual chrome follows the project's design specification (Form controls
// / §06): 1px n-300 border, radius-md, primary-600 focus ring, and a
// chevron positioned with inset-inline-end so it mirrors correctly in RTL.

const UNMAPPED_VALUE = "";

function FieldDropdown({
    id,
    value,
    options,
    onChange,
    disabled = false,
    hasError = false,
    unmappedLabel = "— Unmapped —",
}) {
    const [focused, setFocused] = useState(false);

    const borderColor = hasError
        ? "var(--critical)"
        : focused
          ? "var(--primary-600)"
          : "var(--n-300)";
    const boxShadow = hasError
        ? "var(--ring-critical)"
        : focused
          ? "var(--ring)"
          : "none";

    return (
        <div style={{ position: "relative" }}>
            <select
                id={id}
                data-testid={id}
                value={value ?? UNMAPPED_VALUE}
                disabled={disabled}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                onChange={(event) => {
                    const next = event.target.value;
                    onChange(next === UNMAPPED_VALUE ? null : next);
                }}
                style={{
                    height: "var(--ctl-sm)",
                    width: "100%",
                    padding: "0 34px 0 12px",
                    fontFamily: "var(--font-sans)",
                    fontSize: "14px",
                    borderRadius: "var(--r-md)",
                    border: `1px ${value ? "solid" : "dashed"} ${borderColor}`,
                    boxShadow,
                    outline: "none",
                    appearance: "none",
                    backgroundColor: disabled
                        ? "var(--n-50)"
                        : value
                          ? "var(--n-0)"
                          : "#FCFDFD",
                    color: disabled ? "var(--n-400)" : "var(--n-800)",
                    cursor: disabled ? "not-allowed" : "pointer",
                }}
            >
                <option value={UNMAPPED_VALUE}>{unmappedLabel}</option>
                {options.map((option) => (
                    <option key={option.key} value={option.key}>
                        {option.label}
                        {option.required ? " *" : ""}
                    </option>
                ))}
            </select>
            <span
                aria-hidden="true"
                style={{
                    position: "absolute",
                    top: "50%",
                    insetInlineEnd: "13px",
                    transform: "translateY(-50%)",
                    width: "7px",
                    height: "7px",
                    marginTop: "-3px",
                    borderRight: `1.6px solid ${disabled ? "var(--n-300)" : "var(--n-500)"}`,
                    borderBottom: `1.6px solid ${disabled ? "var(--n-300)" : "var(--n-500)"}`,
                    rotate: "45deg",
                    pointerEvents: "none",
                }}
            />
        </div>
    );
}

export default FieldDropdown;
