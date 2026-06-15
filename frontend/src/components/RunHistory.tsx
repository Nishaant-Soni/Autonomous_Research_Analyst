import { useEffect, useState } from "react";
import { ApiError, listResearch, type ResearchSummary } from "../lib/api";
import { relativeTime } from "../lib/time";

const POLL_MS = 3000;

interface Props {
  selectedSessionId: number | null;
  onSelect: (id: number) => void;
  onNewResearch: () => void;
  refreshKey: number;
}

type Phase = "loading" | "ready" | "error";

const STATUS_STYLES: Record<string, string> = {
  done:        "bg-emerald-100 text-emerald-700",
  failed:      "bg-rose-100 text-rose-700",
  planning:    "bg-indigo-100 text-indigo-700",
  researching: "bg-indigo-100 text-indigo-700",
  critiquing:  "bg-violet-100 text-violet-700",
  writing:     "bg-amber-100 text-amber-700",
  validating:  "bg-amber-100 text-amber-700",
};

const IN_PROGRESS = new Set(["planning", "researching", "critiquing", "writing", "validating"]);

function StatusPill({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {IN_PROGRESS.has(status) && (
        <span className="h-1 w-1 animate-pulse rounded-full bg-current" />
      )}
      {status}
    </span>
  );
}

export function RunHistory({ selectedSessionId, onSelect, onNewResearch, refreshKey }: Props) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [runs, setRuns] = useState<ResearchSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const data = await listResearch(20);
        if (!active) return;
        setRuns(data);
        setPhase("ready");
        setError(null);
      } catch (err) {
        if (!active) return;
        setPhase("error");
        setError(
          err instanceof ApiError
            ? `API ${err.status}: ${err.message}`
            : err instanceof Error
              ? err.message
              : "Unknown error",
        );
      }
    }

    load();
    const handle = setInterval(load, POLL_MS);
    return () => {
      active = false;
      clearInterval(handle);
    };
  }, [refreshKey]);

  return (
    <aside className="flex w-64 flex-none flex-col border-r border-slate-200 bg-white">
      {/* Sidebar header */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Recent runs
        </h2>
        <button
          type="button"
          onClick={onNewResearch}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
            <path d="M5.433 13.917l1.262-3.155A4 4 0 0 1 7.58 9.42l6.92-6.918a2.121 2.121 0 0 1 3 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 0 1-.643-.643z" />
            <path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0 0 10 3H4.75A2.75 2.75 0 0 0 2 5.75v9.5A2.75 2.75 0 0 0 4.75 18h9.5A2.75 2.75 0 0 0 17 15.25V10a.75.75 0 0 0-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5z" />
          </svg>
          New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {phase === "loading" && (
          <div className="flex items-center gap-2 px-4 py-4 text-xs text-slate-400">
            <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading…
          </div>
        )}
        {phase === "error" && (
          <p className="px-4 py-3 text-xs text-rose-600">{error}</p>
        )}
        {phase === "ready" && runs.length === 0 && (
          <div className="px-4 py-8 text-center">
            <p className="text-xs text-slate-400">No runs yet.</p>
            <p className="mt-1 text-xs text-slate-400">Submit a question to get started.</p>
          </div>
        )}
        {phase === "ready" && runs.length > 0 && (
          <ul className="py-1">
            {runs.map((r) => {
              const selected = r.session_id === selectedSessionId;
              return (
                <li key={r.session_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(r.session_id)}
                    className={`group relative w-full px-4 py-3 text-left transition-colors ${
                      selected
                        ? "bg-indigo-50"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    {/* Active indicator bar */}
                    {selected && (
                      <span className="absolute inset-y-0 left-0 w-0.5 rounded-r-full bg-indigo-500" />
                    )}

                    <div className="flex items-start justify-between gap-2">
                      <p className={`line-clamp-2 text-xs leading-relaxed ${selected ? "font-medium text-indigo-900" : "text-slate-700"}`}>
                        {r.question}
                      </p>
                      <StatusPill status={r.status} />
                    </div>

                    <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-slate-400">
                      <span>#{r.session_id}</span>
                      <span>·</span>
                      <span>{relativeTime(r.created_at)}</span>
                      {r.low_confidence && (
                        <>
                          <span>·</span>
                          <span className="rounded bg-amber-50 px-1 py-px font-medium text-amber-600">
                            low confidence
                          </span>
                        </>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-slate-100 px-4 py-2.5">
        <p className="text-[10px] text-slate-400">Auto-refreshes every 3 s</p>
      </div>
    </aside>
  );
}
