import "./StateMessage.css";

/**
 * Reusable state card for loading / error / empty-data states across pages.
 *
 * variant: "loading" | "critical" | "warning" | "unavailable" | "info"
 */
function StateMessage({
    variant = "info",
    icon,
    title,
    message,
    actionLabel,
    onAction,
}) {
    return (
        <div className={`state-message state-message--${variant}`}>
            <div className="state-message-icon">
                {variant === "loading" ? "" : icon}
            </div>

            {title && <h2 className="state-message-title">{title}</h2>}
            {message && <p className="state-message-text">{message}</p>}

            {actionLabel && onAction && (
                <button className="auth-btn-primary" onClick={onAction}>
                    {actionLabel}
                </button>
            )}
        </div>
    );
}

export default StateMessage;
