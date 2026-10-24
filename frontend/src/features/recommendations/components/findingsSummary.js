/**
 * Turning a RecommendationsResult into what the findings strip shows.
 *
 * Every figure here is counted from the payload the API returned. Nothing is
 * inferred, and nothing is shown that the response did not carry.
 */

export const SEVERITIES = ["critical", "warning", "info"];

// Detection failing and detection finding nothing arrive in the same shape but
// mean opposite things, so they are never shown with the same words.
const DETECTION_UNAVAILABLE = "detection_unavailable";

const SEVERITY_WORDS = {
    critical: "critical",
    warning: "warning",
    info: "to know",
};

function countBySeverity(recommendations) {
    const counts = { critical: 0, warning: 0, info: 0 };

    for (const item of recommendations) {
        const severity = item.finding?.severity;

        if (severity in counts) {
            counts[severity] += 1;
        }
    }

    return counts;
}

/**
 * The pills shown above the title, most urgent first, skipping any severity
 * with nothing in it.
 */
export function severityPills(counts) {
    return SEVERITIES.filter((severity) => counts[severity] > 0).map((severity) => ({
        severity,
        label: `${counts[severity]} ${SEVERITY_WORDS[severity]}`,
    }));
}

/**
 * The strip's tone, taken from the most urgent finding present. Drives the
 * border and the rule down its leading edge.
 */
export function summaryTone(counts, total, result) {
    if (counts.critical > 0) return "critical";
    if (counts.warning > 0) return "warning";
    if (total > 0) return "info";
    if (result?.reason === DETECTION_UNAVAILABLE) return "unavailable";
    return "quiet";
}

export function summaryTitle(total, result) {
    if (total > 0) {
        return total === 1
            ? "1 finding needs your attention"
            : `${total} findings need your attention`;
    }

    if (result?.reason === DETECTION_UNAVAILABLE) {
        return "We could not check your data this time";
    }

    return "Nothing stands out in your data";
}

/**
 * The sentence under the title. When there is nothing to report the API sends
 * its own explanation, which is shown as it came rather than reworded.
 */
export function summaryBlurb(result, total) {
    if (total === 0) {
        return result?.message || "Nothing unusual turned up in this data.";
    }

    // Said plainly because the dashboard filters do not narrow this. Findings
    // cover the whole file however the charts above are filtered.
    const base =
        "Covers your whole file. Each one comes with a suggested action in " +
        "the assistant.";
    const held = result?.suppressed_count ?? 0;

    if (held > 0) {
        return `Showing the ${total} most important of ${result.total_findings}. ${base}`;
    }

    return base;
}

/**
 * One concrete line about the most urgent finding, so the strip says something
 * real rather than only counting. Taken from the finding's own message, which
 * detection wrote from the business's rows.
 */
export function summaryHeadline(recommendations) {
    const first = recommendations[0];

    if (!first) {
        return null;
    }

    return first.finding?.message || first.action || null;
}

/**
 * The question the assistant opens with. Phrased so the answer leads with the
 * most serious finding, which is the order the payload is already in.
 */
export function summaryPrompt(total) {
    return total === 1
        ? "Walk me through the finding and what you suggest I do"
        : `Walk me through the ${total} findings, most serious first`;
}

export function summarise(result) {
    const recommendations = result?.recommendations ?? [];
    const total = recommendations.length;
    const counts = countBySeverity(recommendations);

    const ordered = [...recommendations].sort(
        (a, b) =>
            Number(b.finding?.severity === "critical") -
            Number(a.finding?.severity === "critical"),
    );

    return {
        total,
        counts,
        pills: severityPills(counts),
        tone: summaryTone(counts, total, result),
        title: summaryTitle(total, result),
        blurb: summaryBlurb(result, total),
        headline: summaryHeadline(ordered),
        prompt: summaryPrompt(total),
    };
}
