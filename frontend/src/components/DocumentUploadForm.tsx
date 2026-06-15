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
  const [result, setResult] = useState<{
    document_id: number;
    chunks: number;
    name: string;
  } | null>(null);
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
    <details className="group rounded-[24px] border border-white/10 bg-white/[0.03]">
      <summary className="flex cursor-pointer flex-col gap-4 px-5 py-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-200">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 transition-transform group-open:rotate-90">
              <path
                fillRule="evenodd"
                d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06z"
                clipRule="evenodd"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Add reference material</p>
            <p className="mt-1 text-xs leading-6 text-slate-400">
              Upload source notes before the run so private evidence can participate in retrieval.
            </p>
            <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
              Accepted: .txt, .md, .pdf · max 5 MB
            </p>
          </div>
        </div>
      </summary>

      <form onSubmit={handleSubmit} className="space-y-4 border-t border-white/10 px-5 py-5">
        <label className="block">
          <span className="mb-3 block text-xs font-medium uppercase tracking-[0.16em] text-slate-500">
            Choose a document
          </span>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full rounded-2xl border border-dashed border-white/15 bg-slate-950/50 px-4 py-4 text-sm text-slate-300 file:mr-4 file:rounded-xl file:border-0 file:bg-white/10 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white transition hover:border-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={submitting}
          />
        </label>

        {file && (
          <div className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-xs text-slate-300">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-medium text-white">{file.name}</p>
                <p className="mt-1 text-slate-500">{formatBytes(file.size)}</p>
              </div>
              <span className="rounded-full bg-cyan-400/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-cyan-200">
                queued
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-xs leading-6 text-rose-200">
            {error}
          </div>
        )}

        {result && (
          <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-xs leading-6 text-emerald-200">
            Ingested <span className="font-medium text-white">{result.name}</span>. Document #
            {result.document_id} produced {result.chunks} chunks.
          </div>
        )}

        <div className="flex justify-end">
          <button type="submit" disabled={!canSubmit} className="button-secondary sm:min-w-[180px]">
            {submitting ? "Ingesting..." : "Ingest document"}
          </button>
        </div>
      </form>
    </details>
  );
}
