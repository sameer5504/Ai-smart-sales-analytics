import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import FieldDropdown from "./FieldDropdown.jsx";

const OPTIONS = [
    { key: "order_id", label: "Order ID", required: true },
    { key: "category", label: "Category", required: false },
];

describe("FieldDropdown", () => {
    it("renders an unmapped option plus every standard field, marking required ones", () => {
        render(
            <FieldDropdown
                id="dd"
                value={null}
                options={OPTIONS}
                onChange={() => {}}
            />,
        );

        expect(
            screen.getByRole("option", { name: "— Unmapped —" }),
        ).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Order ID *" })).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Category" })).toBeInTheDocument();
    });

    it("reflects the current mapped value", () => {
        render(
            <FieldDropdown
                id="dd"
                value="order_id"
                options={OPTIONS}
                onChange={() => {}}
            />,
        );
        expect(screen.getByTestId("dd")).toHaveValue("order_id");
    });

    it("defaults to the unmapped option when value is null", () => {
        render(
            <FieldDropdown
                id="dd"
                value={null}
                options={OPTIONS}
                onChange={() => {}}
            />,
        );
        expect(screen.getByTestId("dd")).toHaveValue("");
    });

    it("calls onChange with the selected field key", async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <FieldDropdown
                id="dd"
                value={null}
                options={OPTIONS}
                onChange={onChange}
            />,
        );

        await user.selectOptions(screen.getByTestId("dd"), "order_id");

        expect(onChange).toHaveBeenCalledWith("order_id");
    });

    it("calls onChange with null when the user picks the unmapped option", async () => {
        const user = userEvent.setup();
        const onChange = vi.fn();
        render(
            <FieldDropdown
                id="dd"
                value="order_id"
                options={OPTIONS}
                onChange={onChange}
            />,
        );

        await user.selectOptions(screen.getByTestId("dd"), "— Unmapped —");

        expect(onChange).toHaveBeenCalledWith(null);
    });

    it("can be disabled", () => {
        render(
            <FieldDropdown
                id="dd"
                value={null}
                options={OPTIONS}
                onChange={() => {}}
                disabled
            />,
        );
        expect(screen.getByTestId("dd")).toBeDisabled();
    });
});
