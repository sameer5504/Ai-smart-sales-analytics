import "./DataTypeSelect.css";

const DATA_TYPES = [
    { value: "sales", label: "Sales" },
    { value: "customers", label: "Customers" },
    { value: "feedback", label: "Feedback" },
];

function DataTypeSelect({ value, onChange, disabled = false }) {
    return (
        <div className="data-type-field">
            <label className="data-type-label" htmlFor="data-type">
                Data Type
            </label>

            <select
                className="data-type-select"
                id="data-type"
                name="data_type"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                disabled={disabled}
                required
            >
                <option value="" disabled>
                    Select a data type
                </option>

                {DATA_TYPES.map((dataType) => (
                    <option key={dataType.value} value={dataType.value}>
                        {dataType.label}
                    </option>
                ))}
            </select>

            <p className="data-type-hint">
                Select the type of data contained in the uploaded file.
            </p>
        </div>
    );
}

export default DataTypeSelect;
