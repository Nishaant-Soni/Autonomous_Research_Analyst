// Fetch wrapper that adds credentials and handles transparent 401 → refresh → retry.
//
// Single-flight refresh: if multiple in-flight requests all get 401 simultaneously,
// they share one refresh call rather than each firing their own (which would cause the
// second refresh to present an already-used jti and force a logout).

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

let _refreshPromise: Promise<void> | null = null;
let _onAuthFailure: (() => void) | null = null;

export function setAuthFailureCallback(cb: () => void): void {
  _onAuthFailure = cb;
}

function refreshOnce(): Promise<void> {
  if (!_refreshPromise) {
    _refreshPromise = fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((res) => {
        _refreshPromise = null;
        if (!res.ok) throw new Error("refresh failed");
      })
      .catch((err) => {
        _refreshPromise = null;
        throw err;
      });
  }
  return _refreshPromise;
}

export async function authFetch(
  input: string,
  init?: RequestInit,
): Promise<Response> {
  const res = await fetch(input, { ...init, credentials: "include" });
  if (res.status !== 401) return res;

  try {
    await refreshOnce();
  } catch {
    _onAuthFailure?.();
    return res;
  }

  const retried = await fetch(input, { ...init, credentials: "include" });
  if (retried.status === 401) _onAuthFailure?.();
  return retried;
}

// Convenience for EventSource reconnect — returns true if refresh succeeded.
export async function refreshTokens(): Promise<boolean> {
  try {
    await refreshOnce();
    return true;
  } catch {
    _onAuthFailure?.();
    return false;
  }
}
