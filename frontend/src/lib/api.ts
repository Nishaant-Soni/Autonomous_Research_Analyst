// Tiny typed wrapper around the backend's HTTP endpoints. Plain `fetch`; no axios.
//
// VITE_API_URL is exposed at build time (Vite inlines it). In compose we set it to the
// browser-facing URL (http://localhost:8000), NOT the internal Docker hostname, because
// the *browser* makes the request — not the frontend container.

import { authFetch } from "./authFetch";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

// FastAPI returns `detail` as a plain string for raised HTTPExceptions (e.g. "Invalid
// credentials"), but as an array of {loc, msg} objects for 422 request-validation errors.
// Flatten both shapes into one readable string so the UI never renders "[object Object]".
export function errorMessageFromBody(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => {
        const { loc, msg } = d as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
        return field && msg ? `${field}: ${msg}` : (msg ?? "");
      })
      .filter(Boolean);
    if (msgs.length > 0) return msgs.join("; ");
  }
  return fallback;
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
  const res = await authFetch(`${API_URL}${path}`, { ...init, headers });
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
  const res = await authFetch(`${API_URL}/documents/upload`, { method: "POST", body });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || res.statusText);
  }
  return (await res.json()) as DocumentResponse;
}

export interface ResearchDetail {
  session_id: number;
  status: string;
  report_md: string | null;
  citations_valid: boolean | null;
  low_confidence: boolean | null;
  faithfulness: number | null;
  answer_relevancy: number | null;
  hallucination_rate: number | null;
  error: string | null;
}

export async function getResearch(sessionId: number): Promise<ResearchDetail> {
  return request(`/research/${sessionId}`);
}

export interface EvidenceItem {
  claim: string | null;
  content: string | null;
  source_url: string | null;
  source_chunk_id: number | null;
  retriever: string;
}

export async function getEvidence(sessionId: number): Promise<EvidenceItem[]> {
  return request(`/research/${sessionId}/evidence`);
}

export function openResearchStream(sessionId: number): EventSource {
  return new EventSource(`${API_URL}/research/${sessionId}/stream`, { withCredentials: true });
}

export { ApiError };
