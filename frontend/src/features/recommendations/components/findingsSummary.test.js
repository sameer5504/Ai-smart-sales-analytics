import { describe, expect, it } from "vitest";

import { summarise } from "./findingsSummary";

function finding(severity) {
    return { finding: { severity } };
}

function unavailable(reason, message) {
    return {
        status: "unavailable",
        recommendations: [],
        reason,
        message,
    };
}

function available(severities, extra = {}) {
    return {
        status: "available",
        recommendations: severities.map(finding),
        total_findings: severities.length,
        suppressed_count: 0,
        reason: null,
        message: null,
        ...extra,
    };
}

describe("summarise", () => {
    it("counts each severity separately", () => {
        const { counts } = summarise(
            available(["critical", "warning", "warning", "info"]),
        );

        expect(counts).toEqual({ critical: 1, warning: 2, info: 1 });
    });

    it("shows a pill per severity present, most urgent first", () => {
        const { pills } = summarise(available(["info", "critical", "warning"]));

        expect(pills.map((p) => p.label)).toEqual([
            "1 critical",
            "1 warning",
            "1 to know",
        ]);
    });

    it("leaves out a severity that has nothing in it", () => {
        const { pills } = summarise(available(["warning", "warning"]));

        expect(pills.map((p) => p.severity)).toEqual(["warning"]);
    });

    it("takes its tone from the most urgent finding", () => {
        expect(summarise(available(["info", "critical"])).tone).toBe("critical");
        expect(summarise(available(["info", "warning"])).tone).toBe("warning");
        expect(summarise(available(["info"])).tone).toBe("info");
    });

    it("is quiet when there is nothing to report", () => {
        const summary = summarise(
            unavailable("no_findings", "Your numbers look steady."),
        );

        expect(summary.tone).toBe("quiet");
        expect(summary.title).toBe("Nothing stands out in your data");
        expect(summary.blurb).toBe("Your numbers look steady.");
    });

    it("does not claim the data is fine when the check could not run", () => {
        const summary = summarise(
            unavailable("detection_unavailable", "Something broke our side."),
        );

        expect(summary.title).toBe("We could not check your data this time");
        expect(summary.title).not.toContain("Nothing stands out");
        expect(summary.tone).toBe("unavailable");
        expect(summary.blurb).toBe("Something broke our side.");
    });

    it("still says nothing stands out when history was too short", () => {
        const summary = summarise(
            unavailable("insufficient_history", "Not enough history yet."),
        );

        expect(summary.title).toBe("Nothing stands out in your data");
        expect(summary.tone).toBe("quiet");
    });

    it("counts findings in the title, in singular and plural", () => {
        expect(summarise(available(["critical"])).title).toBe(
            "1 finding needs your attention",
        );
        expect(summarise(available(["critical", "info"])).title).toBe(
            "2 findings need your attention",
        );
    });

    it("says how many were held back when the cap applied", () => {
        const summary = summarise(
            available(["critical", "warning"], {
                total_findings: 9,
                suppressed_count: 7,
            }),
        );

        expect(summary.blurb).toContain("2 most important of 9");
    });

    it("says nothing about a cap that did not apply", () => {
        expect(summarise(available(["critical"])).blurb).not.toContain(
            "most important",
        );
    });

    it("says the findings are not narrowed by the dashboard filters", () => {
        expect(summarise(available(["critical"])).blurb).toContain("whole file");
    });

    it("leads with what the most urgent finding actually says", () => {
        const summary = summarise({
            status: "available",
            recommendations: [
                {
                    finding: { severity: "info", message: "A quiet one." },
                    action: "Ignore me.",
                },
                {
                    finding: {
                        severity: "critical",
                        message: "Coffee 250g sold 65% below its usual week.",
                    },
                    action: "Check Coffee 250g.",
                },
            ],
            total_findings: 2,
            suppressed_count: 0,
        });

        expect(summary.headline).toBe("Coffee 250g sold 65% below its usual week.");
    });

    it("falls back to the action when a finding carries no message", () => {
        const summary = summarise({
            status: "available",
            recommendations: [
                { finding: { severity: "critical" }, action: "Restock it." },
            ],
            total_findings: 1,
            suppressed_count: 0,
        });

        expect(summary.headline).toBe("Restock it.");
    });

    it("has no headline when there is nothing to report", () => {
        expect(summarise(unavailable("no_findings", "Steady.")).headline).toBeNull();
    });

    it("asks for the findings in the order they were ranked", () => {
        expect(summarise(available(["critical", "info"])).prompt).toBe(
            "Walk me through the 2 findings, most serious first",
        );
        expect(summarise(available(["critical"])).prompt).toBe(
            "Walk me through the finding and what you suggest I do",
        );
    });

    it("survives a result it was not given", () => {
        const summary = summarise(null);

        expect(summary.total).toBe(0);
        expect(summary.tone).toBe("quiet");
        expect(summary.blurb).toBeTruthy();
    });
});
