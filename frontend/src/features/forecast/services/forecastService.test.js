import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchRevenueForecast } from "./forecastService.js";
import { authFetch } from "../../../shared/utils/authFetch";

vi.mock("../../../shared/utils/authFetch", () => ({
    authFetch: vi.fn(),
}));

function jsonResponse(body, ok = true, status = 200) {
    return { ok, status, json: async () => body };
}

describe("fetchRevenueForecast", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("asks the API once and returns the parsed body", async () => {
        authFetch.mockResolvedValue(jsonResponse({ status: "available" }));

        await expect(fetchRevenueForecast(7)).resolves.toEqual({
            status: "available",
        });
        expect(authFetch).toHaveBeenCalledTimes(1);
        expect(authFetch.mock.calls[0][0]).toContain("dataset_id=7");
    });

    it("shares one request between callers asking at the same time", async () => {
        let settle;
        authFetch.mockReturnValue(
            new Promise((resolve) => {
                settle = () => resolve(jsonResponse({ status: "available" }));
            }),
        );

        const first = fetchRevenueForecast(7);
        const second = fetchRevenueForecast(7);
        settle();

        await expect(first).resolves.toEqual({ status: "available" });
        await expect(second).resolves.toEqual({ status: "available" });
        expect(authFetch).toHaveBeenCalledTimes(1);
    });

    it("keeps different datasets apart", async () => {
        authFetch.mockResolvedValue(jsonResponse({ status: "available" }));

        await Promise.all([fetchRevenueForecast(1), fetchRevenueForecast(2)]);

        expect(authFetch).toHaveBeenCalledTimes(2);
    });

    it("asks again once the previous request has settled", async () => {
        authFetch.mockResolvedValue(jsonResponse({ status: "available" }));

        await fetchRevenueForecast(7);
        await fetchRevenueForecast(7);

        expect(authFetch).toHaveBeenCalledTimes(2);
    });

    it("does not hold a failed request open", async () => {
        authFetch.mockResolvedValueOnce(jsonResponse({ detail: "nope" }, false, 500));
        await expect(fetchRevenueForecast(7)).rejects.toThrow("nope");

        authFetch.mockResolvedValueOnce(jsonResponse({ status: "available" }));
        await expect(fetchRevenueForecast(7)).resolves.toEqual({
            status: "available",
        });
        expect(authFetch).toHaveBeenCalledTimes(2);
    });
});
