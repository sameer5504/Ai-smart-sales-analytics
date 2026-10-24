// Uploading the same display filename twice (possibly with a different
// mapping/currency) is intentional - each upload is its own independent
// dataset. Datasets sharing a filename get a stable sequence number
// (oldest = 1) plus a full date+time; a filename that appears only once is
// left exactly as-is. Shared by DatasetSelector and the My Files page so
// both show the same disambiguated names.
export function withDisambiguation(datasets) {
    const countByName = {};
    for (const d of datasets) {
        countByName[d.filename] = (countByName[d.filename] ?? 0) + 1;
    }

    // The list is already sorted newest-first (created_at DESC), so walking
    // it in reverse assigns "1" to the oldest upload of a given filename.
    const nextIndexByName = {};
    const indexById = {};
    for (const d of [...datasets].reverse()) {
        if (countByName[d.filename] > 1) {
            nextIndexByName[d.filename] = (nextIndexByName[d.filename] ?? 0) + 1;
            indexById[d.id] = nextIndexByName[d.filename];
        }
    }

    return datasets.map((d) => {
        const isDuplicate = countByName[d.filename] > 1;
        return {
            ...d,
            displayName: isDuplicate
                ? `${d.filename} (${indexById[d.id]})`
                : d.filename,
            isDuplicate,
        };
    });
}

export function formatRelativeDate(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";

    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.round(diffMs / 60000);
    const diffHours = Math.round(diffMinutes / 60);
    const diffDays = Math.round(diffHours / 24);

    if (diffMinutes < 1) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Full, unambiguous date+time (e.g. "Sep 6, 4:17 PM") - used instead of the
// vague relative time whenever several uploads share the same display
// filename.
export function formatFullDateTime(isoString) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}
