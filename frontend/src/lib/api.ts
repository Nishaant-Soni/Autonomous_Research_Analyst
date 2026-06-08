// Tiny typed wrapper around the backend's HTTP endpoints. Plain `fetch`; no axios.
//
// VITE_API_URL is exposed at build time (Vite inlines it). In compose we set it to the
// browser-facing URL (http://localhost:8000), NOT the internal Docker hostname, because
// the *browser* makes the request — not the frontend container.

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Only attach Content-Type when there's actually a body — otherwise we'd turn
  // bodyless GETs (like /health) into preflighted CORS requests for no reason and
  // flood the API log with spurious OPTIONS calls.
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (init?.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<{ status: string }> {
  return request("/health");
}

export interface ResearchSummary {
  session_id: number;
  question: string;
  status: string;
  low_confidence: boolean;
  created_at: string; // ISO 8601
  completed_at: string | null;
}

export async function listResearch(limit = 20): Promise<ResearchSummary[]> {
  return request(`/research?limit=${limit}`);
}

export interface ResearchResponse {
  session_id: number;
}

export async function postResearch(question: string): Promise<ResearchResponse> {
  return request("/research", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export interface DocumentResponse {
  document_id: number;
  chunks: number;
}

export async function postDocument(args: {
  raw_text: string;
  title?: string;
}): Promise<DocumentResponse> {
  return request("/documents", { method: "POST", body: JSON.stringify(args) });
}

// Multipart upload — the browser sets Content-Type with the boundary automatically, so
// we MUST omit our default JSON content-type header for this path.
export async function postDocumentFile(file: File): Promise<DocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_URL}/documents/upload`, { method: "POST", body });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }
  return (await res.json()) as DocumentResponse;
}

export { ApiError };
