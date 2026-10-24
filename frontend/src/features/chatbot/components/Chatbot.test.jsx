import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Chatbot from "./Chatbot";

vi.mock("../services/chatbotService", () => ({
    sendChatbotQuestion: vi.fn(),
    streamChatbotQuestion: vi.fn(),
}));

// The assistant reads the selected dataset from context, which AppLayout
// provides in the real app. These tests are about the question the dashboard
// sends across, so the selection is stood in for rather than mounted.
vi.mock("../../../shared/context/DatasetContext", () => ({
    useDatasetContext: () => ({
        datasetId: 7,
        currentDataset: { id: 7, filename: "sales.csv", currency: "GBP" },
    }),
}));

const OPENING = "Walk me through the 3 findings, most serious first";

function drawWith(state) {
    return render(
        <MemoryRouter initialEntries={[{ pathname: "/assistant", state }]}>
            <Chatbot />
        </MemoryRouter>,
    );
}

describe("Chatbot", () => {
    it("types the dashboard's question into the box without sending it", async () => {
        drawWith({ prompt: OPENING });

        expect(screen.getByRole("textbox")).toHaveValue(OPENING);
        expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
    });

    it("says where the question came from", () => {
        drawWith({ prompt: OPENING });

        expect(screen.getByText("Started from your dashboard")).toBeInTheDocument();
    });

    it("lets the user drop the question and start again", async () => {
        drawWith({ prompt: OPENING });

        await userEvent.click(screen.getByRole("button", { name: "Clear" }));

        expect(screen.getByRole("textbox")).toHaveValue("");
        expect(
            screen.queryByText("Started from your dashboard"),
        ).not.toBeInTheDocument();
    });

    it("leaves the box empty when the user came here on their own", () => {
        drawWith(undefined);

        expect(screen.getByRole("textbox")).toHaveValue("");
        expect(
            screen.queryByText("Started from your dashboard"),
        ).not.toBeInTheDocument();
    });

    it("keeps the question editable before it is sent", async () => {
        drawWith({ prompt: OPENING });

        const box = screen.getByRole("textbox");

        await userEvent.clear(box);
        await userEvent.type(box, "Just the urgent one please");

        expect(box).toHaveValue("Just the urgent one please");
        expect(screen.getByText("Started from your dashboard")).toBeInTheDocument();
    });
});
