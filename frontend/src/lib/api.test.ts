import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchHealth, postResearch, ApiError, errorMessageFromBody } from "./api";

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

  it("surfaces a parsed FastAPI detail, not raw JSON", async () => {
    mockFetch.mockResolvedValue(
      errorResponse(400, JSON.stringify({ detail: "file too large; max 5 MB" })),
    );
    const err = await fetchHealth().catch((e) => e);
    expect((err as ApiError).message).toBe("file too large; max 5 MB");
  });

  it("surfaces the slowapi rate-limit (429) error message", async () => {
    mockFetch.mockResolvedValue(
      errorResponse(429, JSON.stringify({ error: "Rate limit exceeded: 10 per 1 minute" })),
    );
    const err = await fetchHealth().catch((e) => e);
    expect((err as ApiError).message).toBe("Rate limit exceeded: 10 per 1 minute");
  });

  it("keeps the raw text for non-JSON error bodies", async () => {
    mockFetch.mockResolvedValue(errorResponse(502, "Bad Gateway"));
    const err = await fetchHealth().catch((e) => e);
    expect((err as ApiError).message).toBe("Bad Gateway");
  });
});

describe("errorMessageFromBody", () => {
  it("returns a string detail as-is (HTTPException shape)", () => {
    expect(errorMessageFromBody({ detail: "Invalid credentials" }, "fallback")).toBe(
      "Invalid credentials",
    );
  });

  it("flattens a 422 validation array to 'field: msg' (the password-too-short case)", () => {
    const body = {
      detail: [
        {
          type: "string_too_short",
          loc: ["body", "password"],
          msg: "String should have at least 8 characters",
        },
      ],
    };
    expect(errorMessageFromBody(body, "fallback")).toBe(
      "password: String should have at least 8 characters",
    );
  });

  it("joins multiple validation errors", () => {
    const body = {
      detail: [
        { loc: ["body", "email"], msg: "value is not a valid email address" },
        { loc: ["body", "password"], msg: "String should have at least 8 characters" },
      ],
    };
    expect(errorMessageFromBody(body, "fallback")).toBe(
      "email: value is not a valid email address; password: String should have at least 8 characters",
    );
  });

  it("returns slowapi's top-level error string (429 shape)", () => {
    expect(
      errorMessageFromBody({ error: "Rate limit exceeded: 5 per 1 minute" }, "fallback"),
    ).toBe("Rate limit exceeded: 5 per 1 minute");
  });

  it("falls back when detail is absent, empty, or null", () => {
    expect(errorMessageFromBody({}, "fallback")).toBe("fallback");
    expect(errorMessageFromBody(null, "fallback")).toBe("fallback");
    expect(errorMessageFromBody({ detail: [] }, "fallback")).toBe("fallback");
  });
});
