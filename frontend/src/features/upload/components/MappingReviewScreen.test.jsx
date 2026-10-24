import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MappingReviewScreen from "./MappingReviewScreen.jsx";
import {
    MappingValidationApiError,
    applyMapping,
    fetchMappingSchema,
    submitMapping,
    suggestMapping,
} from "../services/mappingService.js";
import { useDatasetContext } from "../../../shared/context/DatasetContext.jsx";

vi.mock("../services/mappingService.js", async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual,
        fetchMappingSchema: vi.fn(),
        suggestMapping: vi.fn(),
        submitMapping: vi.fn(),
        applyMapping: vi.fn(),
    };
});

// useMapping() reads the active dataset's currency from DatasetContext (see
// shared/context/DatasetContext.jsx) - these tests render MappingReviewScreen
// on its own, with no real <DatasetProvider> above it, so the hook itself is
// mocked here instead of standing up the whole provider (which would also
// need a mocked GET /api/datasets call just to satisfy this component test).
vi.mock("../../../shared/context/DatasetContext.jsx", () => ({
    useDatasetContext: vi.fn(),
}));

const SCHEMA = [
    { key: "transaction_date", label: "Transaction Date", required: true },
    { key: "order_id", label: "Order ID", required: true },
    { key: "product_id", label: "Product ID", required: true },
    { key: "product_name", label: "Product Name", required: true },
    { key: "quantity", label: "Quantity", required: true },
    { key: "unit_price", label: "Unit Price", required: true },
    { key: "category", label: "Category", required: false },
];

const SUGGESTIONS = [
    { column: "Order Date", field: "transaction_date", confidence: 0.95 },
    { column: "Order No", field: "order_id", confidence: 0.95 },
    { column: "SKU", field: "product_id", confidence: 0.9 },
    { column: "Item", field: "product_name", confidence: 0.9 },
    { column: "Qty", field: "quantity", confidence: 0.9 },
    { column: "Unit Price ($)", field: "unit_price", confidence: 0.95 },
    { column: "Notes", field: null, confidence: 0.2 },
];

function renderScreen(props) {
    return render(
        <MemoryRouter>
            <MappingReviewScreen {...props} />
        </MemoryRouter>,
    );
}

async function goToReviewScreen(user) {
    renderScreen();
    await screen.findByRole("button", { name: "Detect Mapping" });
    const textbox = screen.getByLabelText("Detected columns");
    await user.clear(textbox);
    await user.type(textbox, SUGGESTIONS.map((s) => s.column).join(", "));
    await user.click(screen.getByRole("button", { name: "Detect Mapping" }));
    await screen.findByRole("button", { name: "Submit Mapping" });
}

describe("MappingReviewScreen", () => {
    beforeEach(() => {
        fetchMappingSchema.mockResolvedValue(SCHEMA);
        suggestMapping.mockResolvedValue(SUGGESTIONS);
        useDatasetContext.mockReturnValue({
            currentDataset: { currency: "SAR" },
            refresh: vi
                .fn()
                .mockResolvedValue([{ id: 1, filename: "sales.csv", currency: "SAR" }]),
            selectDataset: vi.fn(),
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it("loads the schema and starts on the column-input screen", async () => {
        renderScreen();
        expect(
            await screen.findByRole("button", { name: "Detect Mapping" }),
        ).toBeInTheDocument();
    });

    it("moves to the review screen with columns mapped from the automatic suggestions", async () => {
        const user = userEvent.setup();
        await goToReviewScreen(user);

        expect(
            screen.getByText("Order Date", { selector: "label" }),
        ).toBeInTheDocument();
        expect(screen.getByTestId("field-Order Date")).toHaveValue("transaction_date");
        expect(screen.getByTestId("field-Notes")).toHaveValue("");
        expect(screen.getByText("Unmapped")).toBeInTheDocument();
    });

    it("shows a required-field warning when a required field has no column mapped", async () => {
        const user = userEvent.setup();
        await goToReviewScreen(user);

        // Un-map the column currently satisfying the required "quantity" field.
        await user.selectOptions(screen.getByTestId("field-Qty"), "— Unmapped —");

        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Missing required fields: Quantity",
        );
    });

    it("submits the mapping and shows a success state, disabling further submits", async () => {
        const user = userEvent.setup();
        submitMapping.mockResolvedValue({
            success: true,
            message: "Mapping is valid.",
            mapping: {},
        });
        await goToReviewScreen(user);

        const submitButton = screen.getByRole("button", { name: "Submit Mapping" });
        await user.click(submitButton);

        expect(await screen.findByRole("status")).toHaveTextContent(
            "Mapping submitted successfully.",
        );
        expect(screen.getByRole("button", { name: "Submitted" })).toBeDisabled();
        expect(submitMapping).toHaveBeenCalledTimes(1);
    });

    it("shows a loading state while submitting and ignores extra clicks", async () => {
        const user = userEvent.setup();
        let resolveSubmit;
        submitMapping.mockReturnValue(
            new Promise((resolve) => {
                resolveSubmit = resolve;
            }),
        );
        await goToReviewScreen(user);

        const submitButton = screen.getByRole("button", { name: "Submit Mapping" });
        await user.click(submitButton);
        await user.click(submitButton); // extra click while submitting should be a no-op

        expect(
            await screen.findByRole("button", { name: "Submitting…" }),
        ).toBeDisabled();
        expect(submitMapping).toHaveBeenCalledTimes(1);

        resolveSubmit({ success: true });
        await screen.findByRole("status");
    });

    it("displays structured backend validation errors and preserves the selected mapping", async () => {
        const user = userEvent.setup();
        submitMapping.mockRejectedValue(
            new MappingValidationApiError({ missing_required_fields: ["unit_price"] }),
        );
        await goToReviewScreen(user);

        await user.click(screen.getByRole("button", { name: "Submit Mapping" }));

        const alerts = await screen.findAllByRole("alert");
        expect(
            alerts.some((el) =>
                el.textContent.includes("Missing required fields: Unit Price"),
            ),
        ).toBe(true);

        // Selections must still be there so the user can fix things without starting over.
        expect(screen.getByTestId("field-Order Date")).toHaveValue("transaction_date");
        expect(screen.getByRole("button", { name: "Submit Mapping" })).toBeEnabled();
    });

    it("displays a generic error message on network/server failure and preserves the mapping", async () => {
        const user = userEvent.setup();
        submitMapping.mockRejectedValue(
            new Error("Network error: could not reach the server. Please try again."),
        );
        await goToReviewScreen(user);

        await user.click(screen.getByRole("button", { name: "Submit Mapping" }));

        expect(
            await screen.findByText(/could not reach the server/i),
        ).toBeInTheDocument();
        expect(screen.getByTestId("field-Order Date")).toHaveValue("transaction_date");
    });
});

describe("MappingReviewScreen finishing a real upload", () => {
    const FINISH_PROPS = {
        filename: "sales.csv",
        dataType: "sales",
        currency: "SAR",
        initialColumns: SUGGESTIONS.map((s) => s.column),
    };

    beforeEach(() => {
        fetchMappingSchema.mockResolvedValue(SCHEMA);
        suggestMapping.mockResolvedValue(SUGGESTIONS);
        useDatasetContext.mockReturnValue({
            currentDataset: { currency: "SAR" },
            refresh: vi
                .fn()
                .mockResolvedValue([{ id: 1, filename: "sales.csv", currency: "SAR" }]),
            selectDataset: vi.fn(),
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    it("skips straight to the review screen pre-filled from the failed upload's columns", async () => {
        renderScreen(FINISH_PROPS);

        expect(
            await screen.findByRole("button", { name: "Submit Mapping" }),
        ).toBeInTheDocument();
        expect(suggestMapping).toHaveBeenCalledWith(FINISH_PROPS.initialColumns);
        expect(screen.getByTestId("field-Order Date")).toHaveValue("transaction_date");
        // The paste-your-columns screen is skipped entirely for a real upload.
        expect(screen.queryByLabelText("Detected columns")).not.toBeInTheDocument();
    });

    it("finishes the upload through /api/mapping/apply and offers to continue", async () => {
        const user = userEvent.setup();
        applyMapping.mockResolvedValue({
            stored: true,
            row_count: 3,
            filename: "sales.csv",
            message: "file uploaded successfully",
        });
        renderScreen(FINISH_PROPS);
        await screen.findByRole("button", { name: "Submit Mapping" });

        await user.click(screen.getByRole("button", { name: "Submit Mapping" }));

        expect(await screen.findByRole("status")).toHaveTextContent(
            "File processed successfully.",
        );
        expect(applyMapping).toHaveBeenCalledWith(
            "sales.csv",
            "sales",
            "SAR",
            FINISH_PROPS.initialColumns,
            expect.objectContaining({ "Order Date": "transaction_date" }),
        );
        expect(
            screen.getByRole("button", { name: "Go to your dashboard" }),
        ).toBeInTheDocument();
        expect(submitMapping).not.toHaveBeenCalled();
    });

    it("reports a structurally invalid mapping the same way the standalone tool does", async () => {
        const user = userEvent.setup();
        applyMapping.mockRejectedValue(
            new MappingValidationApiError({ missing_required_fields: ["unit_price"] }),
        );
        renderScreen(FINISH_PROPS);
        await screen.findByRole("button", { name: "Submit Mapping" });

        await user.click(screen.getByRole("button", { name: "Submit Mapping" }));

        const alerts = await screen.findAllByRole("alert");
        expect(
            alerts.some((el) =>
                el.textContent.includes("Missing required fields: Unit Price"),
            ),
        ).toBe(true);
        expect(screen.getByRole("button", { name: "Submit Mapping" })).toBeEnabled();
    });
});
