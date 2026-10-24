import { useNavigate } from "react-router-dom";

import { useRecommendations } from "../hooks/useRecommendations";
import { summarise } from "./findingsSummary";
import "./FindingsPanel.css";

const PILL_ICONS = {
    critical: "✕",
    warning: "!",
    info: "i",
};

/**
 * The way in to the recommendations, above the numbers they are about.
 *
 * Counts come from the API response and nothing is worked out here, so what
 * the strip claims and what the assistant goes on to say cannot disagree.
 */
function FindingsPanel({ datasetId }) {
    const navigate = useNavigate();
    const { result, isLoading, failed } = useRecommendations(datasetId);

    if (failed) {
        return null;
    }

    if (isLoading || !result) {
        return (
            <div className="findings-panel findings-panel--quiet">
                <div className="findings-panel__body" aria-busy="true">
                    <p className="findings-panel__loading">
                        Looking for anything that needs your attention
                    </p>
                </div>
            </div>
        );
    }

    const { total, pills, tone, title, blurb, headline, prompt } = summarise(result);

    return (
        <section
            className={`findings-panel findings-panel--${tone}`}
            aria-labelledby="findings-panel-title"
        >
            <div className="findings-panel__body">
                {pills.length > 0 && (
                    <div className="findings-panel__pills">
                        {pills.map((pill) => (
                            <span
                                key={pill.severity}
                                className={`findings-pill findings-pill--${pill.severity}`}
                            >
                                <span aria-hidden="true">
                                    {PILL_ICONS[pill.severity]}
                                </span>
                                {pill.label}
                            </span>
                        ))}
                    </div>
                )}

                <h2 className="findings-panel__title" id="findings-panel-title">
                    {title}
                </h2>

                {headline && <p className="findings-panel__headline">{headline}</p>}

                <p className="findings-panel__blurb">{blurb}</p>
            </div>

            {total > 0 && (
                <div className="findings-panel__action">
                    <button
                        type="button"
                        className="findings-panel__button"
                        onClick={() => navigate("/assistant", { state: { prompt } })}
                    >
                        Open in the assistant &rarr;
                    </button>

                    <span className="findings-panel__hint">
                        Opens with the question already typed, unsent.
                    </span>
                </div>
            )}
        </section>
    );
}

export default FindingsPanel;
