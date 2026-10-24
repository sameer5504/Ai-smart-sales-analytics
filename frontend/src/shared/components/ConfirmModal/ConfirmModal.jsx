import { useEffect, useRef } from "react";
import "./ConfirmModal.css";

/**
 * Generic confirm/cancel modal. Not tied to datasets - any feature can
 * reuse this for a destructive-action confirmation.
 */
export default function ConfirmModal({
    open,
    title,
    message,
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    isConfirming = false,
    tone = "critical",
    onConfirm,
    onCancel,
}) {
    const dialogRef = useRef(null);

    useEffect(() => {
        if (!open) return undefined;

        function handleEscape(event) {
            if (event.key === "Escape" && !isConfirming) onCancel?.();
        }
        document.addEventListener("keydown", handleEscape);

        dialogRef.current?.focus();

        return () => document.removeEventListener("keydown", handleEscape);
    }, [open, isConfirming, onCancel]);

    if (!open) return null;

    return (
        <div
            className="confirm-modal__overlay"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget && !isConfirming) {
                    onCancel?.();
                }
            }}
        >
            <div
                className="confirm-modal"
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-modal-title"
                aria-describedby="confirm-modal-message"
                tabIndex={-1}
                ref={dialogRef}
            >
                <h2 id="confirm-modal-title" className="confirm-modal__title">
                    {title}
                </h2>
                <p id="confirm-modal-message" className="confirm-modal__message">
                    {message}
                </p>
                <div className="confirm-modal__actions">
                    <button
                        type="button"
                        className="confirm-modal__button confirm-modal__button--cancel"
                        onClick={onCancel}
                        disabled={isConfirming}
                    >
                        {cancelLabel}
                    </button>
                    <button
                        type="button"
                        className={`confirm-modal__button confirm-modal__button--${tone}`}
                        onClick={onConfirm}
                        disabled={isConfirming}
                    >
                        {isConfirming ? "Working…" : confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
