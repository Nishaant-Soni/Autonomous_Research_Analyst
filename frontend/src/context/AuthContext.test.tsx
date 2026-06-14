import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { AuthProvider, useAuth } from "./AuthContext";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function mockResponse(status: number, body?: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: () => Promise.resolve(body),
    text: () =>
      Promise.resolve(typeof body === "string" ? body : JSON.stringify(body ?? "")),
  };
}

function Probe() {
  const { user, loading } = useAuth();
  return (
    <div
      data-testid="probe"
      data-loading={String(loading)}
      data-email={user?.email ?? ""}
    />
  );
}

async function waitFor(check: () => void, timeoutMs = 1000): Promise<void> {
  const started = Date.now();
  while (true) {
    try {
      check();
      return;
    } catch (err) {
      if (Date.now() - started > timeoutMs) throw err;
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });
    }
  }
}

describe("AuthProvider", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    mockFetch.mockReset();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  it("rehydrates the user after /auth/me 401s and refresh succeeds", async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(401, { detail: "Not authenticated" }))
      .mockResolvedValueOnce(mockResponse(200, { ok: true }))
      .mockResolvedValueOnce(
        mockResponse(200, { user_id: 7, email: "nishaant@example.com" }),
      );

    await act(async () => {
      root.render(
        <AuthProvider>
          <Probe />
        </AuthProvider>,
      );
    });

    await waitFor(() => {
      const probe = container.querySelector("[data-testid='probe']");
      expect(probe?.getAttribute("data-loading")).toBe("false");
      expect(probe?.getAttribute("data-email")).toBe("nishaant@example.com");
    });

    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(mockFetch.mock.calls[0]?.[0]).toContain("/auth/me");
    expect(mockFetch.mock.calls[1]?.[0]).toContain("/auth/refresh");
    expect(mockFetch.mock.calls[2]?.[0]).toContain("/auth/me");
    expect(mockFetch.mock.calls[0]?.[1]).toMatchObject({ credentials: "include" });
    expect(mockFetch.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      credentials: "include",
    });
    expect(mockFetch.mock.calls[2]?.[1]).toMatchObject({ credentials: "include" });
  });
});
