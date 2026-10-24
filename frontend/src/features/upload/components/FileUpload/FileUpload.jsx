import { useState, useRef } from "react";
import { validateFile } from "../../../../shared/utils/fileValidation";
import "./FileUpload.css";

const CURRENCIES = [
    { code: "SAR", label: "SAR", sublabel: "Saudi Riyal" },
    { code: "ILS", label: "ILS", sublabel: "Israeli Shekel" },
    { code: "USD", label: "USD", sublabel: "US Dollar" },
    { code: "EUR", label: "EUR", sublabel: "Euro" },
];

function FileUpload({ onFileSelect, onCurrencyChange, currency = "" }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");
    const inputRef = useRef(null);

    const handleFileChange = (file) => {
        if (!file) return;

        const result = validateFile(file);

        if (!result.valid) {
            setErrorMessage(result.message);
            setSelectedFile(null);
            return;
        }

        setErrorMessage("");
        setSelectedFile(file);
        if (onFileSelect) onFileSelect(file);
    };

    const handleInputChange = (e) => {
        handleFileChange(e.target.files[0]);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFileChange(e.dataTransfer.files[0]);
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleClick = () => {
        inputRef.current.click();
    };

    return (
        <div className="file-upload-container">
            <div
                className={`file-upload-dropzone ${isDragging ? "dragging" : ""}`}
                onClick={handleClick}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleInputChange}
                    className="file-upload-input"
                />
                {selectedFile ? (
                    <p className="file-upload-filename">📄 {selectedFile.name}</p>
                ) : (
                    <p>Drag a file here or click to select (Excel or CSV)</p>
                )}
            </div>

            <div className="file-upload-currency">
                <span className="file-upload-currency-label">
                    Currency in this file
                </span>

                <div
                    className="file-upload-currency-group"
                    role="group"
                    aria-label="Currency"
                >
                    {CURRENCIES.map((c) => {
                        const isActive = currency === c.code;
                        return (
                            <button
                                key={c.code}
                                type="button"
                                className={`file-upload-currency-button ${
                                    isActive ? "file-upload-currency-button-active" : ""
                                }`}
                                onClick={() => onCurrencyChange?.(c.code)}
                                aria-pressed={isActive}
                            >
                                <span className="file-upload-currency-code">
                                    {c.label}
                                </span>
                                <span className="file-upload-currency-sublabel">
                                    {c.sublabel}
                                </span>
                            </button>
                        );
                    })}
                </div>

                {!currency && (
                    <p className="file-upload-currency-hint">
                        Select the currency your file's amounts are in.
                    </p>
                )}
            </div>

            {errorMessage && <p className="file-upload-error">{errorMessage}</p>}
        </div>
    );
}

export default FileUpload;
