import { useEffect, useState } from "react";
import { ApiError, listResearch, type ResearchSummary } from "../lib/api";
import { relativeTime } from "../lib/time";

const POLL_MS = 3000;

interface Props {
  selectedSessionId: number | null;
  onSelect: (id: number) => void;
  // Bumping this counter from the parent (e.g. on a new submit) forces an immediate
  // refresh so newly-started runs show up without waiting for the next 3-second tick.
  refreshKey: number;
}

type Phase = "loading" | "ready" | "error";

const STATUS_STYLES: Record<string, string> = {
  done: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
  planning: "bg-sky-100 text-sky-700",
  researching: "bg-sky-100 text-sky-700",
  critiquing: "bg-violet-100 text-violet-700",
  writing: "bg-amber-100 text-amber-700",
  validating: "bg-amber-100 text-amber-700",
};

function statusPill(status: string) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}>
      {status}
    </span>
  );
}

// Plan 5.7 (Group B prep): recent-runs sidebar. Polls `GET /research?limit=20` every 3s
// and lets the user click between past runs. The detail panel reading `selectedSessionId`
// arrives with the rest of Group B (SSE timeline + report + evidence).
export function RunHistory({ selectedSessionId, onSelect, refreshKey }: Props) {
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
    <aside className="flex h-full flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">Recent runs</h2>
        <p className="text-xs text-slate-500">Auto-refreshes every 3 s</p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {phase === "loading" && (
          <p className="px-4 py-3 text-sm text-slate-500">Loading…</p>
        )}
        {phase === "error" && (
          <p className="px-4 py-3 text-sm text-rose-700">{error}</p>
        )}
        {phase === "ready" && runs.length === 0 && (
          <p className="px-4 py-6 text-sm text-slate-500">
            No runs yet. Submit a question to get started.
          </p>
        )}
        {phase === "ready" && runs.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {runs.map((r) => {
              const selected = r.session_id === selectedSessionId;
              return (
                <li key={r.session_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(r.session_id)}
                    className={`w-full px-4 py-3 text-left transition hover:bg-slate-50 ${
                      selected ? "bg-slate-100" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="line-clamp-2 text-sm text-slate-900">{r.question}</p>
                      {statusPill(r.status)}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      #{r.session_id} · {relativeTime(r.created_at)}
                      {r.low_confidence && (
                        <span className="ml-1.5 rounded bg-amber-50 px-1 py-px text-[10px] font-medium text-amber-700">
                          low confidence
                        </span>
                      )}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
