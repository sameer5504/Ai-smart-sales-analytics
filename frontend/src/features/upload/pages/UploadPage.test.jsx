import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import UploadPage from "./UploadPage.jsx";
import { uploadFile } from "../services/uploadService";

vi.mock("../services/uploadService", () => ({
    uploadFile: vi.fn(),
}));

const COLUMNS = ["Order Date", "Order No", "SKU", "Item", "Qty", "Unit Price"];

function uploadResponse(overrides = {}) {
    return {
        filename: "sales.csv",
        data_type: "sales",
        size_kb: 1.2,
        extension: ".csv",
        stored: true,
        row_count: 3,
        columns: COLUMNS,
        validation: { is_valid: true, missing_required_fields: [] },
        data_quality: { rows_read: 3, rows_kept: 3 },
        ...overrides,
    };
}

// The currency is passed to the mapping step via route state now (see
// useUpload.js/uploadService.js), not sessionStorage - this stub surfaces
// whatever state actually arrived so a test can assert on it directly.
function MappingStepStub() {
    const location = useLocation();
    return (
        <div>
            mapping step
            <span data-testid="passed-currency">{location.state?.currency ?? ""}</span>
        </div>
    );
}

// Renders the upload page behind a router that reports where it navigated to,
// so these tests assert the step the user actually lands on.
function renderUploadPage() {
    return render(
        <MemoryRouter initialEntries={["/upload"]}>
            <Routes>
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/mapping" element={<MappingStepStub />} />
                <Route path="/dashboard" element={<div>dashboard</div>} />
            </Routes>
        </MemoryRouter>,
    );
}

async function selectFileAndUpload(user) {
    const file = new File(["Order Date\n2026-07-03\n"], "sales.csv", {
        type: "text/csv",
    });
    // Set the file directly rather than clicking it: the drop zone opens the
    // hidden input on click, so a synthesised click on the input re-enters
    // that handler instead of picking a file.
    fireEvent.change(document.querySelector('input[type="file"]'), {
        target: { files: [file] },
    });
    await user.click(screen.getByRole("button", { name: /SAR/ }));
    await user.click(screen.getByRole("button", { name: /upload file/i }));
}

describe("UploadPage handing off to the mapping step", () => {
    beforeEach(() => {
        sessionStorage.clear();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    // The regression this guards: mapping used to be offered only when the
    // automatic matcher failed (stored === false), so a file whose columns
    // happened to match never reached the review step at all.
    it("continues to the mapping review even when the automatic match succeeded", async () => {
        const user = userEvent.setup();
        uploadFile.mockResolvedValue(uploadResponse({ stored: true }));
        renderUploadPage();

        await selectFileAndUpload(user);

        expect(await screen.findByText("mapping step")).toBeInTheDocument();
    });

    it("continues to the mapping review when required columns could not be matched", async () => {
        const user = userEvent.setup();
        uploadFile.mockResolvedValue(
            uploadResponse({
                stored: false,
                row_count: 0,
                validation: {
                    is_valid: false,
                    missing_required_fields: ["unit_price"],
                },
            }),
        );
        renderUploadPage();

        await selectFileAndUpload(user);

        expect(await screen.findByText("mapping step")).toBeInTheDocument();
    });

    it("passes the chosen currency via route state instead of sessionStorage", async () => {
        const user = userEvent.setup();
        uploadFile.mockResolvedValue(uploadResponse());
        renderUploadPage();

        await selectFileAndUpload(user);

        await screen.findByText("mapping step");
        expect(screen.getByTestId("passed-currency")).toHaveTextContent("SAR");
        // Currency now belongs to the dataset (set at upload time, stored in
        // the datasets table) - it's never written to sessionStorage, which
        // used to hold one global value shared across every uploaded file.
        expect(sessionStorage.getItem("uploadedCurrency")).toBeNull();
        expect(sessionStorage.getItem("hasUploadedData")).toBeNull();
    });

    it("stays on the upload page and reports a failed upload", async () => {
        const user = userEvent.setup();
        uploadFile.mockRejectedValue(
            new Error("Only CSV and Excel files are supported"),
        );
        renderUploadPage();

        await selectFileAndUpload(user);

        expect(
            await screen.findByText(/Only CSV and Excel files are supported/),
        ).toBeInTheDocument();
        expect(screen.queryByText("mapping step")).not.toBeInTheDocument();
    });
});
