import { useEffect, useState } from "react";
import { fetchRecommendations } from "../services/recommendationsService";

/**
 * Load the recommendations for a dataset, once per dataset.
 *
 * What was loaded is kept together with the dataset it belongs to, so the
 * loading and failed flags are worked out from that rather than set on the
 * way in. Switching datasets therefore reads as loading straight away instead
 * of showing the previous one's findings for a frame.
 *
 * A failure here is deliberately quiet. The findings strip is a way in to the
 * assistant rather than something the dashboard depends on, so a dataset that
 * has not been prepared leaves the strip out instead of putting an error in
 * front of numbers that loaded perfectly well.
 */
export function useRecommendations(datasetId) {
    const [loaded, setLoaded] = useState(null);

    useEffect(() => {
        if (!datasetId) {
            return;
        }

        let current = true;

        fetchRecommendations(datasetId)
            .then((data) => {
                if (current) {
                    setLoaded({ datasetId, result: data, failed: false });
                }
            })
            .catch(() => {
                if (current) {
                    setLoaded({ datasetId, result: null, failed: true });
                }
            });

        return () => {
            current = false;
        };
    }, [datasetId]);

    const isCurrent = Boolean(datasetId) && loaded?.datasetId === datasetId;

    return {
        result: isCurrent ? loaded.result : null,
        isLoading: Boolean(datasetId) && !isCurrent,
        failed: isCurrent ? loaded.failed : false,
    };
}
