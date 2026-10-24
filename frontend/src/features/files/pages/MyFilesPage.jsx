import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDatasetContext } from "../../../shared/context/DatasetContext";
import ConfirmModal from "../../../shared/components/ConfirmModal/ConfirmModal";
import {
    withDisambiguation,
    formatFullDateTime,
} from "../../../shared/utils/datasetDisplay";
import "./MyFilesPage.css";

export default function MyFilesPage() {
    const { datasets, isLoading, error, selectDataset, deleteDataset } =
        useDatasetContext();
    const navigate = useNavigate();

    const [pendingDelete, setPendingDelete] = useState(null); // dataset or null
    const [isDeleting, setIsDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState("");

    const rows = withDisambiguation(datasets);

    function openDataset(id) {
        selectDataset(id);
        navigate("/dashboard");
    }

    async function confirmDelete() {
        if (!pendingDelete) return;
        setIsDeleting(true);
        setDeleteError("");
        try {
            await deleteDataset(pendingDelete.id);
            setPendingDelete(null);
        } catch (err) {
            setDeleteError(err.message);
        } finally {
            setIsDeleting(false);
        }
    }

    return (
        <div className="my-files-page">
            <h1 className="my-files-page__title">My Files</h1>
            <p className="my-files-page__subtitle">
                Every file you've uploaded. Open one to view its dashboard, or remove it
                if you no longer need it.
            </p>

            {isLoading && <p className="my-files-page__state">Loading your files…</p>}

            {error && (
                <p className="my-files-page__state my-files-page__state--error">
                    {error}
                </p>
            )}

            {!isLoading && !error && rows.length === 0 && (
                <p className="my-files-page__state">
                    You haven't uploaded any files yet.
                </p>
            )}

            {!isLoading && !error && rows.length > 0 && (
                <div className="my-files-table-wrap">
                    <table className="my-files-table">
                        <thead>
                            <tr>
                                <th>File</th>
                                <th>Uploaded</th>
                                <th>Rows</th>
                                <th>Currency</th>
                                <th aria-label="Actions" />
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((dataset) => (
                                <tr key={dataset.id}>
                                    <td>
                                        <button
                                            type="button"
                                            className="my-files-table__name-button"
                                            onClick={() => openDataset(dataset.id)}
                                        >
                                            {dataset.displayName}
                                        </button>
                                    </td>
                                    <td className="my-files-table__muted">
                                        {formatFullDateTime(dataset.created_at)}
                                    </td>
                                    <td className="my-files-table__muted">
                                        {dataset.row_count != null
                                            ? dataset.row_count.toLocaleString()
                                            : "—"}
                                    </td>
                                    <td className="my-files-table__muted">
                                        {dataset.currency || "—"}
                                    </td>
                                    <td className="my-files-table__actions">
                                        <button
                                            type="button"
                                            className="my-files-table__open-button"
                                            onClick={() => openDataset(dataset.id)}
                                        >
                                            Open
                                        </button>
                                        <button
                                            type="button"
                                            className="my-files-table__delete-button"
                                            onClick={() => {
                                                setDeleteError("");
                                                setPendingDelete(dataset);
                                            }}
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <ConfirmModal
                open={Boolean(pendingDelete)}
                title="Delete this file?"
                message={
                    pendingDelete
                        ? `"${pendingDelete.displayName}" and its dashboard data will be permanently deleted. This can't be undone.`
                        : ""
                }
                confirmLabel="Delete"
                isConfirming={isDeleting}
                tone="critical"
                onConfirm={confirmDelete}
                onCancel={() => {
                    if (!isDeleting) setPendingDelete(null);
                }}
            />

            {deleteError && (
                <p className="my-files-page__state my-files-page__state--error">
                    {deleteError}
                </p>
            )}
        </div>
    );
}
