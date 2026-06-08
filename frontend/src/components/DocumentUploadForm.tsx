import { useRef, useState } from "react";
import { ApiError, postDocumentFile } from "../lib/api";

const ACCEPTED = ".txt,.md,.pdf";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

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
      setError(
        err instanceof ApiError
          ? `API ${err.status}: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <details className="group rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-5 py-3.5 text-sm font-medium text-slate-600 hover:text-slate-900">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4 text-slate-400 transition-transform group-open:rotate-90"
        >
          <path
            fillRule="evenodd"
            d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06z"
            clipRule="evenodd"
          />
        </svg>
        Add a reference document
        <span className="ml-auto text-xs font-normal text-slate-400">optional · .txt .md .pdf · max 5 MB</span>
      </summary>

      <form onSubmit={handleSubmit} className="space-y-3.5 border-t border-slate-100 px-5 py-4">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-600 file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-indigo-600 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={submitting}
        />

        {file && (
          <p className="flex items-center gap-1.5 text-xs text-slate-500">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5 text-slate-400">
              <path d="M3 3.5A1.5 1.5 0 0 1 4.5 2h4.879a1.5 1.5 0 0 1 1.06.44l2.122 2.12A1.5 1.5 0 0 1 13 5.622V12.5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 12.5v-9z" />
            </svg>
            {file.name}
            <span className="text-slate-400">({formatBytes(file.size)})</span>
          </p>
        )}

        {error && (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {error}
          </p>
        )}
        {result && (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            Ingested <span className="font-mono font-medium">{result.name}</span> — document #{result.document_id} · {result.chunks} chunks
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Ingesting…" : "Ingest document"}
        </button>
      </form>
    </details>
  );
}
