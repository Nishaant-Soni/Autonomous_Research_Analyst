import { useRef, useState } from "react";
import { ApiError, postDocumentFile } from "../lib/api";

const ACCEPTED = ".txt,.md,.pdf";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

// Plan 5.2 (Group A follow-up): real file uploads — .txt / .md / .pdf. The browser sends
// multipart/form-data to `POST /documents/upload`; the server extracts text (pypdf for
// PDFs, utf-8 decode for txt/md), chunks + embeds, and returns the document_id + chunk
// count. PDFs work because the API container has pypdf in its runtime deps.
export function DocumentUploadForm() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ document_id: number; chunks: number; name: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = file !== null && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || submitting) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const out = await postDocumentFile(file);
      setResult({ ...out, name: file.name });
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `API ${err.status}: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Unknown error";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <details className="rounded-md border border-slate-200 bg-white">
      <summary className="cursor-pointer select-none px-4 py-2.5 text-sm font-medium text-slate-700 hover:text-slate-900">
        Add a reference document (optional)
      </summary>
      <form onSubmit={handleSubmit} className="space-y-3 border-t border-slate-200 p-4">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">
            Document file{" "}
            <span className="font-normal text-slate-500">(.txt, .md, .pdf — max 5 MB)</span>
          </span>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={submitting}
          />
        </label>
        {file && (
          <p className="text-xs text-slate-600">
            Selected: <span className="font-mono">{file.name}</span> ({formatBytes(file.size)})
          </p>
        )}
        {error && (
          <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </p>
        )}
        {result && (
          <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            Ingested <span className="font-mono">{result.name}</span> as document #
            {result.document_id} ({result.chunks} chunks).
          </p>
        )}
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Ingesting…" : "Ingest document"}
        </button>
      </form>
    </details>
  );
}
