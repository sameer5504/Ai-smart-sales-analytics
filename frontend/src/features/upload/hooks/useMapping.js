import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    MappingValidationApiError,
    applyMapping,
    fetchMappingSchema,
    submitMapping,
    suggestMapping,
} from "../services/mappingService.js";
import { useDatasetContext } from "../../../shared/context/DatasetContext";

const SAMPLE_COLUMNS =
    "Order Date, Order No, SKU, Item, Qty, Unit Price ($), Product Category, Notes";

function parseColumnsInput(text) {
    return text
        .split(/[\n,]/)
        .map((value) => value.trim())
        .filter((value) => value.length > 0);
}

// Groups the current mapping by standard field so we can flag fields
// claimed by more than one column, and find required fields with none.
function summariseMapping(mapping, schema) {
    const fieldToColumns = {};
    for (const [column, field] of Object.entries(mapping)) {
        if (!field) continue;
        if (!fieldToColumns[field]) fieldToColumns[field] = [];
        fieldToColumns[field].push(column);
    }

    const duplicateFields = Object.fromEntries(
        Object.entries(fieldToColumns).filter(([, cols]) => cols.length > 1),
    );

    const missingRequired = schema
        .filter((field) => field.required && !fieldToColumns[field.key])
        .map((field) => field.key);

    return { fieldToColumns, duplicateFields, missingRequired };
}

// Business logic and API communication for the manual column mapping
// screen, kept separate from MappingReviewScreen's presentation per the
// project's Page -> Hook -> Service -> API layering (see useUpload.js).
//
// Called with no arguments, this is the standalone mapping tool: the user
// types or pastes column headers and only validates a mapping's shape.
//
// Called with { filename, dataType, initialColumns } - what UploadPage sends
// when an upload's required columns could not be auto-matched - it skips
// straight to the review screen pre-filled with the automatic matcher's
// best guesses for that file's real columns, and submitting actually
// finishes the upload: it calls /api/mapping/apply, which re-runs the same
// saved file through the pipeline /api/upload uses, with the confirmed
// mapping in place of the automatic guess that fell short.
export function useMapping({ filename, dataType, initialColumns, currency } = {}) {
    const navigate = useNavigate();
    // The dataset the dashboard/chatbot show is decided by DatasetContext,
    // not sessionStorage - a freshly finished upload has to refresh its
    // list and switch to the new file itself, or it stays invisible until
    // the next full page load re-fetches /api/datasets on its own.
    const { refresh: refreshDatasets, selectDataset } = useDatasetContext();
    const isFinishingUpload = Boolean(filename && initialColumns?.length);

    const [schema, setSchema] = useState(null);
    const [schemaError, setSchemaError] = useState(null);

    const [phase, setPhase] = useState(isFinishingUpload ? "loading" : "input");
    const [columnsText, setColumnsText] = useState(SAMPLE_COLUMNS);
    const [columns, setColumns] = useState([]);
    const [mapping, setMapping] = useState({});

    const [detecting, setDetecting] = useState(false);
    const [detectError, setDetectError] = useState(null);

    const [submitState, setSubmitState] = useState("idle"); // 'idle' | 'submitting' | 'success' | 'error'
    const [submitErrors, setSubmitErrors] = useState(null);
    const [submitErrorMessage, setSubmitErrorMessage] = useState(null);
    const [uploadResult, setUploadResult] = useState(null);

    useEffect(() => {
        let cancelled = false;
        fetchMappingSchema()
            .then((fields) => {
                if (!cancelled) setSchema(fields);
            })
            .catch((err) => {
                if (!cancelled) setSchemaError(err.message);
            });
        return () => {
            cancelled = true;
        };
    }, []);

    // Arriving here with a failed upload's real columns: pre-fill the review
    // screen with the automatic matcher's best guesses for them instead of
    // making the user retype what /api/upload already parsed.
    useEffect(() => {
        if (!isFinishingUpload) return;

        let cancelled = false;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setDetecting(true);

        setDetectError(null);
        suggestMapping(initialColumns)
            .then((suggestions) => {
                if (cancelled) return;
                const initial = {};
                for (const suggestion of suggestions) {
                    initial[suggestion.column] = suggestion.field ?? null;
                }
                setColumns(initialColumns);
                setMapping(initial);
                setPhase("review");
            })
            .catch((err) => {
                if (!cancelled) setDetectError(err.message);
            })
            .finally(() => {
                if (!cancelled) setDetecting(false);
            });
        return () => {
            cancelled = true;
        };
        // Only re-runs if the upload we're finishing changes, not on every
        // render - initialColumns arrives as a fresh array from route state.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isFinishingUpload, filename]);

    const summary = useMemo(
        () =>
            schema
                ? summariseMapping(mapping, schema)
                : { fieldToColumns: {}, duplicateFields: {}, missingRequired: [] },
        [mapping, schema],
    );

    async function handleDetect() {
        const parsedColumns = parseColumnsInput(columnsText);
        if (parsedColumns.length === 0) {
            setDetectError("Enter at least one column name.");
            return;
        }

        setDetecting(true);
        setDetectError(null);
        try {
            const suggestions = await suggestMapping(parsedColumns);
            const initialMapping = {};
            for (const suggestion of suggestions) {
                initialMapping[suggestion.column] = suggestion.field ?? null;
            }
            setColumns(parsedColumns);
            setMapping(initialMapping);
            setSubmitState("idle");
            setSubmitErrors(null);
            setSubmitErrorMessage(null);
            setPhase("review");
        } catch (err) {
            setDetectError(err.message);
        } finally {
            setDetecting(false);
        }
    }

    function handleMappingChange(column, field) {
        setMapping((prev) => ({ ...prev, [column]: field }));
    }

    const [confirmingReset, setConfirmingReset] = useState(false);

    async function handleStartOver() {
        if (detecting) return;

        if (isFinishingUpload) {
            if (!confirmingReset) {
                setConfirmingReset(true);
                return;
            }
            setConfirmingReset(false);

            setDetecting(true);
            setDetectError(null);
            try {
                const suggestions = await suggestMapping(initialColumns);
                const initial = {};
                for (const suggestion of suggestions) {
                    initial[suggestion.column] = suggestion.field ?? null;
                }
                setColumns(initialColumns);
                setMapping(initial);
                setSubmitState("idle");
                setSubmitErrors(null);
                setSubmitErrorMessage(null);
                setPhase("review");
            } catch (err) {
                setDetectError(err.message);
            } finally {
                setDetecting(false);
            }
        } else {
            setPhase("input");
            setColumns([]);
            setMapping({});
            setSubmitState("idle");
            setSubmitErrors(null);
            setSubmitErrorMessage(null);
        }
    }

    function handleCancelReset() {
        setConfirmingReset(false);
    }
    async function handleSubmit() {
        // Guard against duplicate submissions (double-click, slow network, etc).
        if (submitState === "submitting") return;

        setSubmitState("submitting");
        setSubmitErrors(null);
        setSubmitErrorMessage(null);

        try {
            if (isFinishingUpload) {
                const result = await applyMapping(
                    filename,
                    dataType,
                    currency,
                    columns,
                    mapping,
                );
                setUploadResult(result);
                if (result.stored) {
                    // The rows exist only once a confirmed mapping has been
                    // applied - that's also the moment this dataset first
                    // shows up in GET /api/datasets. Refresh the shared
                    // dataset list and switch to it, so the dashboard/chatbot
                    // open the file we just finished uploading instead of
                    // staying on whatever was selected before.
                    const refreshedDatasets = await refreshDatasets();
                    const newDataset = refreshedDatasets?.find(
                        (d) => d.filename === result.filename,
                    );
                    if (newDataset) {
                        selectDataset(newDataset.id);
                    }
                    setSubmitState("success");
                } else {
                    // The mapping validated (every required field is mapped), so
                    // this only happens if the file itself had no usable rows left -
                    // report it rather than claiming the upload finished.
                    setSubmitErrorMessage(result.message);
                    setSubmitState("error");
                }
            } else {
                await submitMapping(columns, mapping);
                setSubmitState("success");
            }
        } catch (err) {
            // Selections in `mapping` are intentionally left untouched so the
            // user can fix the problem without re-entering everything.
            if (err instanceof MappingValidationApiError) {
                setSubmitErrors(err.errors);
            } else {
                setSubmitErrorMessage(err.message);
            }
            setSubmitState("error");
        }
    }

    function handleContinue() {
        if (uploadResult?.filename) {
            // The dataset was already selected in DatasetContext back in
            // handleSubmit, the moment the upload finished - the dashboard
            // just needs to open now.
            navigate("/dashboard");
        }
    }

    return {
        schema,
        schemaError,
        phase,
        columnsText,
        setColumnsText,
        columns,
        mapping,
        detecting,
        detectError,
        submitState,
        submitErrors,
        submitErrorMessage,
        uploadResult,
        isFinishingUpload,
        summary,
        handleDetect,
        handleMappingChange,
        confirmingReset,
        handleCancelReset,
        handleStartOver,
        handleSubmit,
        handleContinue,
    };
}
