import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchHealth, postResearch, ApiError } from "./api";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function okResponse(body: unknown) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(""),
  };
}

function errorResponse(status: number, body = "") {
  return {
    ok: false,
    status,
    statusText: "Error",
    json: () => Promise.resolve(null),
    text: () => Promise.resolve(body),
  };
}

describe("api", () => {
  beforeEach(() => mockFetch.mockReset());

  it("fetchHealth returns parsed JSON", async () => {
    mockFetch.mockResolvedValue(okResponse({ status: "ok" }));
    expect(await fetchHealth()).toEqual({ status: "ok" });
  });

  it("GET does not set Content-Type", async () => {
    mockFetch.mockResolvedValue(okResponse({ status: "ok" }));
    await fetchHealth();
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect((init?.headers as Record<string, string>)?.["Content-Type"]).toBeUndefined();
  });

  it("POST sets Content-Type: application/json", async () => {
    mockFetch.mockResolvedValue(okResponse({ session_id: 1 }));
    await postResearch("test question");
    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("throws ApiError with status on non-ok response", async () => {
    mockFetch.mockResolvedValue(errorResponse(404, "not found"));
    const err = await fetchHealth().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
  });
});
