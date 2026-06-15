import { useEffect, useState } from "react";
import {
  ApiError,
  getResearch,
  listResearch,
  type ResearchDetail,
  type ResearchSummary,
} from "../lib/api";
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
  done: "bg-emerald-400/12 text-emerald-200 ring-emerald-400/20",
  failed: "bg-rose-400/12 text-rose-200 ring-rose-400/20",
  planning: "bg-cyan-400/12 text-cyan-200 ring-cyan-400/20",
  researching: "bg-sky-400/12 text-sky-200 ring-sky-400/20",
  critiquing: "bg-violet-400/12 text-violet-200 ring-violet-400/20",
  writing: "bg-amber-400/12 text-amber-200 ring-amber-400/20",
  validating: "bg-fuchsia-400/12 text-fuchsia-200 ring-fuchsia-400/20",
};

const IN_PROGRESS = new Set([
  "planning",
  "researching",
  "critiquing",
  "writing",
  "validating",
]);

function StatusPill({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-700/60 text-slate-300 ring-white/10";
  return (
    <span className={`status-pill ring-1 ${cls}`}>
      {IN_PROGRESS.has(status) && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {status}
    </span>
  );
}

export function RunHistory({
  selectedSessionId,
  onSelect,
  onNewResearch,
  refreshKey,
}: Props) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [runs, setRuns] = useState<ResearchSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ResearchDetail | null>(null);

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

  useEffect(() => {
    let active = true;

    if (selectedSessionId === null) {
      setSelectedDetail(null);
      return () => {
        active = false;
      };
    }

    getResearch(selectedSessionId)
      .then((data) => {
        if (active) setSelectedDetail(data);
      })
      .catch(() => {
        if (active) setSelectedDetail(null);
      });

    return () => {
      active = false;
    };
  }, [selectedSessionId, refreshKey]);

  return (
    <aside className="panel min-h-[300px] w-full overflow-hidden lg:w-[20rem] lg:flex-none">
      <div className="border-b border-white/10 px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow">Recent sessions</p>
            <h2 className="mt-2 text-xl font-semibold text-white">Run history</h2>
            <p className="mt-1 text-xs leading-6 text-slate-400">
              Review earlier investigations or start a fresh brief.
            </p>
          </div>
          <button type="button" onClick={onNewResearch} className="button-secondary shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path d="M10 4.25a.75.75 0 0 1 .75.75v4.25H15a.75.75 0 0 1 0 1.5h-4.25V15a.75.75 0 0 1-1.5 0v-4.25H5a.75.75 0 0 1 0-1.5h4.25V5a.75.75 0 0 1 .75-.75z" />
            </svg>
            New
          </button>
        </div>
      </div>

      <div className="max-h-[55vh] overflow-y-auto scrollbar-thin lg:max-h-[calc(100vh-17rem)]">
        {phase === "loading" && (
          <div className="flex items-center gap-3 px-5 py-5 text-sm text-slate-400">
            <svg className="h-4 w-4 animate-spin text-cyan-300" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading session history...
          </div>
        )}

        {phase === "error" && (
          <div className="px-5 py-5">
            <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-xs leading-6 text-rose-200">
              {error}
            </div>
          </div>
        )}

        {phase === "ready" && runs.length === 0 && (
          <div className="px-5 py-10 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-6 w-6">
                <path d="M10 2a.75.75 0 0 1 .75.75v6.69l2.22-2.22a.75.75 0 1 1 1.06 1.06l-3.5 3.5a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 0 1 1.06-1.06l2.22 2.22V2.75A.75.75 0 0 1 10 2z" />
                <path d="M3.5 13.25a.75.75 0 0 1 .75.75v.5c0 .69.56 1.25 1.25 1.25h9a1.25 1.25 0 0 0 1.25-1.25V14a.75.75 0 0 1 1.5 0v.5A2.75 2.75 0 0 1 14.5 17h-9A2.75 2.75 0 0 1 2.75 14.5V14a.75.75 0 0 1 .75-.75z" />
              </svg>
            </div>
            <p className="mt-4 text-sm font-medium text-slate-200">No runs yet</p>
            <p className="mt-2 text-xs leading-6 text-slate-400">
              Start a research brief and it will appear here within a few seconds.
            </p>
          </div>
        )}

        {phase === "ready" && runs.length > 0 && (
          <ul className="space-y-2 px-3 py-3">
            {runs.map((run) => {
              const selected = run.session_id === selectedSessionId;
              return (
                <li key={run.session_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(run.session_id)}
                    className={`w-full rounded-[22px] border px-4 py-4 text-left transition duration-200 ${
                      selected
                        ? "border-cyan-300/30 bg-cyan-400/10 shadow-[0_18px_36px_rgba(6,182,212,0.08)]"
                        : "border-white/5 bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.05]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="line-clamp-2 text-sm font-medium leading-6 text-slate-100">
                          {run.question}
                        </p>
                      </div>
                      <StatusPill status={run.status} />
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                      <span>{relativeTime(run.created_at)}</span>
                      {selected &&
                        selectedDetail?.status === "done" &&
                        selectedDetail.citations_valid === true && (
                          <span className="rounded-full bg-emerald-400/10 px-2 py-1 text-emerald-200">
                            citations valid
                          </span>
                        )}
                      {run.low_confidence && (
                        <span className="rounded-full bg-amber-400/10 px-2 py-1 text-amber-200">
                          low confidence
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="border-t border-white/10 px-5 py-3">
        <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
          Refreshes every 3 seconds
        </p>
      </div>
    </aside>
  );
}
