import { useState } from "react";
import { generateReport } from "../services/reportsService";

// Business logic for saving the Dashboard's current view as a downloadable
// report, kept separate from the button's presentation per the project's
// Page -> Hook -> Service -> API layering (see useDashboard.js).
export function useGenerateReport() {
    const [isGenerating, setIsGenerating] = useState(false);
    const [generateError, setGenerateError] = useState("");
    const [lastGeneratedAt, setLastGeneratedAt] = useState(null);

    const generate = async (data) => {
        if (isGenerating) return;

        setIsGenerating(true);
        setGenerateError("");

        try {
            const report = await generateReport(data);
            setLastGeneratedAt(report.generated_at);
            return report;
        } catch (error) {
            setGenerateError(error.message);
            return null;
        } finally {
            setIsGenerating(false);
        }
    };

    return {
        generate,
        isGenerating,
        generateError,
        lastGeneratedAt,
    };
}
