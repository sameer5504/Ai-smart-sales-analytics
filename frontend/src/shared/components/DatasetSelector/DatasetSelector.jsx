import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDatasetContext } from "../../context/DatasetContext";
import {
    withDisambiguation,
    formatRelativeDate,
    formatFullDateTime,
} from "../../utils/datasetDisplay";
import "./DatasetSelector.css";

/**
 * uploadPath: route to send the person to for uploading new data.
 * Defaults to "/upload" - change this prop (or the default below) if your
 * app's actual upload route is named differently in App.jsx.
 */
export default function DatasetSelector({ uploadPath = "/upload" }) {
    const { datasets, datasetId, currentDataset, selectDataset, isLoading, error } =
        useDatasetContext();
    const [open, setOpen] = useState(false);
    const containerRef = useRef(null);
    const navigate = useNavigate();

    const disambiguatedDatasets = useMemo(
        () => withDisambiguation(datasets),
        [datasets],
    );

    const currentDisplay = disambiguatedDatasets.find((d) => d.id === datasetId);

    useEffect(() => {
        function handleClickOutside(event) {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setOpen(false);
            }
        }
        function handleEscape(event) {
            if (event.key === "Escape") setOpen(false);
        }
        document.addEventListener("mousedown", handleClickOutside);
        document.addEventListener("keydown", handleEscape);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("keydown", handleEscape);
        };
    }, []);

    function goToUpload() {
        setOpen(false);
        navigate(uploadPath);
    }

    // Picking a file only changes which dataset is "selected" in context -
    // on a page that doesn't display any dataset's data (e.g. /upload),
    // that's invisible, so it looked like the dropdown "did nothing".
    // Navigating to the dashboard makes the result of the choice visible
    // no matter which page the person picked from.
    function handleSelect(id) {
        selectDataset(id);
        setOpen(false);
        navigate("/dashboard");
    }

    if (isLoading) {
        return (
            <div
                className="dataset-selector dataset-selector--loading"
                aria-busy="true"
            >
                <span className="dataset-selector__skeleton" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="dataset-selector dataset-selector--error">
                Couldn't load your files
            </div>
        );
    }

    if (!datasets.length) {
        return (
            <button
                type="button"
                className="dataset-selector__upload-only"
                onClick={goToUpload}
            >
                <PlusIcon />
                Upload data
            </button>
        );
    }

    return (
        <div className="dataset-selector" ref={containerRef}>
            <button
                type="button"
                className="dataset-selector__trigger"
                onClick={() => setOpen((prev) => !prev)}
                aria-haspopup="listbox"
                aria-expanded={open}
            >
                <FileIcon />
                <span className="dataset-selector__label">
                    {currentDisplay?.displayName ??
                        currentDataset?.filename ??
                        "Select a file"}
                </span>
                <ChevronIcon open={open} />
            </button>

            {open && (
                <div className="dataset-selector__menu" role="listbox">
                    <div className="dataset-selector__menu-heading">Your files</div>

                    <div className="dataset-selector__list">
                        {disambiguatedDatasets.map((dataset) => (
                            <button
                                key={dataset.id}
                                type="button"
                                role="option"
                                aria-selected={dataset.id === datasetId}
                                className={
                                    dataset.id === datasetId
                                        ? "dataset-selector__item dataset-selector__item--active"
                                        : "dataset-selector__item"
                                }
                                onClick={() => handleSelect(dataset.id)}
                            >
                                <FileIcon />
                                <span className="dataset-selector__item-text">
                                    <span className="dataset-selector__item-name">
                                        {dataset.displayName}
                                    </span>
                                    <span className="dataset-selector__item-meta">
                                        {dataset.isDuplicate
                                            ? formatFullDateTime(dataset.created_at)
                                            : formatRelativeDate(dataset.created_at)}
                                        {dataset.row_count != null
                                            ? ` · ${dataset.row_count.toLocaleString()} rows`
                                            : ""}
                                    </span>
                                </span>
                                {dataset.id === datasetId && <CheckIcon />}
                            </button>
                        ))}
                    </div>

                    <div className="dataset-selector__divider" />

                    <button
                        type="button"
                        className="dataset-selector__upload"
                        onClick={goToUpload}
                    >
                        <PlusIcon />
                        Upload new data
                    </button>
                </div>
            )}
        </div>
    );
}

function FileIcon() {
    return (
        <svg
            className="dataset-selector__icon"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
        >
            <path
                d="M5 2.5h6.5L15 6v10.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1Z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
            />
            <path
                d="M11.5 2.5V6H15"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
            />
        </svg>
    );
}

function ChevronIcon({ open }) {
    return (
        <svg
            className={
                open
                    ? "dataset-selector__chevron dataset-selector__chevron--open"
                    : "dataset-selector__chevron"
            }
            viewBox="0 0 20 20"
            width="14"
            height="14"
            fill="none"
            aria-hidden="true"
        >
            <path
                d="M5 7.5 10 12.5 15 7.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

function PlusIcon() {
    return (
        <svg
            className="dataset-selector__icon"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
        >
            <path
                d="M10 4.5v11M4.5 10h11"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
            />
        </svg>
    );
}

function CheckIcon() {
    return (
        <svg
            className="dataset-selector__check"
            viewBox="0 0 20 20"
            width="16"
            height="16"
            fill="none"
            aria-hidden="true"
        >
            <path
                d="M4.5 10.5 8 14l7.5-8"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}
