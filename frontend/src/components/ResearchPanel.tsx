import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getEvidence, getResearch, openResearchStream, type EvidenceItem } from "../lib/api";
import { refreshTokens } from "../lib/authFetch";

// ── Pipeline stages (order matters for the timeline) ──────────────────────────

const STAGES = [
  { key: "planning", label: "Planning" },
  { key: "researching", label: "Researching" },
  { key: "critiquing", label: "Critiquing" },
  { key: "writing", label: "Writing" },
  { key: "validating", label: "Validating" },
  { key: "done", label: "Done" },
] as const;

const TERMINAL = new Set(["done", "failed"]);

// ── Build a citation-ordered evidence list from the report's ## Sources block ──
//
// The citation validator renders "[n] <url-or-chunk-#id>" lines. We parse those to get
// the sources in citation order, then match each back to a fetched EvidenceItem by
// source_url (web) or source_chunk_id (rag). This gives us:
//   - only cited items (not all the uncited evidence the researcher gathered)
//   - in [1..k] citation order so clicking [n] in the report maps to panel row n

function buildCitedEvidence(
  reportMd: string,
  all: EvidenceItem[],
): EvidenceItem[] {
  const sourcesMatch = reportMd.match(/^##\s*Sources\s*\n([\s\S]*)$/im);
  if (!sourcesMatch) return all;

  const cited: EvidenceItem[] = [];
  for (const line of sourcesMatch[1].split("\n")) {
    const m = line.match(/^\[(\d+)\]\s+(.+)$/);
    if (!m) continue;
    const ref = m[2].trim();
    let found: EvidenceItem | undefined;
    if (ref.startsWith("chunk #")) {
      const chunkId = parseInt(ref.slice(7), 10);
      found = all.find((e) => e.source_chunk_id === chunkId);
    } else {
      found = all.find((e) => e.source_url === ref);
    }
    if (found) cited.push(found);
  }
  return cited.length > 0 ? cited : all;
}

// ── Citation transform: turns "[n]" text inside ReactMarkdown into clickable buttons ──

function transformCitations(
  children: React.ReactNode,
  onClick: (n: number) => void,
): React.ReactNode {
  return React.Children.map(children, (child) => {
    if (typeof child !== "string") return child;
    const parts = child.split(/(\[\d+\])/g);
    if (parts.length === 1) return child;
    return parts.map((part, i) => {
      const m = part.match(/^\[(\d+)\]$/);
      if (m) {
        const n = parseInt(m[1], 10);
        return (
          <button
            key={i}
            type="button"
            onClick={() => onClick(n)}
            className="mx-0.5 inline-flex rounded bg-indigo-50 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-indigo-600 transition-colors hover:bg-indigo-100 hover:text-indigo-800"
          >
            {part}
          </button>
        );
      }
      return part;
    });
  });
}

// ── Progress timeline (5.3) ────────────────────────────────────────────────────

function ProgressTimeline({ status }: { status: string }) {
  const currentIdx = STAGES.findIndex((s) => s.key === status);

  return (
    <div className="rounded-xl bg-white px-6 py-4 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start">
        {STAGES.map((stage, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <React.Fragment key={stage.key}>
              <div className="flex flex-col items-center gap-1.5">
                <div className="relative">
                  {active && (
                    <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400 opacity-50" />
                  )}
                  <div
                    className={`relative flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold ${
                      done
                        ? "bg-emerald-500 text-white"
                        : active
                          ? "bg-indigo-600 text-white"
                          : "bg-slate-100 text-slate-400"
                    }`}
                  >
                    {done ? "✓" : i + 1}
                  </div>
                </div>
                <span
                  className={`text-[10px] font-medium ${
                    active ? "text-indigo-700" : done ? "text-slate-500" : "text-slate-400"
                  }`}
                >
                  {stage.label}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <div
                  className={`mx-1 mt-3.5 h-px flex-1 transition-colors ${done ? "bg-emerald-300" : "bg-slate-200"}`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ── Evidence panel (5.5) ───────────────────────────────────────────────────────

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  highlightN: number | null;
  itemRefs: React.MutableRefObject<(HTMLDivElement | null)[]>;
}

function EvidencePanel({ evidence, highlightN, itemRefs }: EvidencePanelProps) {
  return (
    <div className="flex flex-col rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="border-b border-slate-100 px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Sources
        </h2>
        <p className="mt-0.5 text-[10px] text-slate-400">Click [n] in the report to highlight</p>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin divide-y divide-slate-50" style={{ maxHeight: "60vh" }}>
        {evidence.length === 0 && (
          <p className="px-4 py-6 text-center text-xs text-slate-400">No sources available.</p>
        )}
        {evidence.map((ev, i) => (
          <div
            key={i}
            ref={(el) => { itemRefs.current[i] = el; }}
            className={`px-4 py-3 transition-colors duration-500 ${
              highlightN === i + 1 ? "bg-indigo-50" : "hover:bg-slate-50"
            }`}
          >
            <div className="flex items-start gap-2.5">
              <span className={`mt-0.5 flex-none rounded-md px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                highlightN === i + 1
                  ? "bg-indigo-100 text-indigo-600"
                  : "bg-slate-100 text-slate-500"
              }`}>
                [{i + 1}]
              </span>
              <div className="min-w-0 flex-1 space-y-1.5">
                {ev.claim && (
                  <p className="line-clamp-2 text-xs font-medium leading-relaxed text-slate-700">
                    {ev.claim}
                  </p>
                )}
                <p className="line-clamp-3 text-[11px] leading-relaxed text-slate-500">{ev.content}</p>
                <div className="flex items-center gap-2 pt-0.5">
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
                      ev.retriever === "web"
                        ? "bg-sky-100 text-sky-600"
                        : "bg-violet-100 text-violet-600"
                    }`}
                  >
                    {ev.retriever}
                  </span>
                  {ev.source_url && (
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="min-w-0 truncate text-[10px] text-slate-400 hover:text-indigo-600 hover:underline"
                    >
                      {ev.source_url}
                    </a>
                  )}
                  {ev.source_chunk_id != null && !ev.source_url && (
                    <span className="text-[10px] text-slate-400">chunk #{ev.source_chunk_id}</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ResearchPanel (orchestrates 5.3 + 5.4 + 5.5) ─────────────────────────────

interface Props {
  sessionId: number;
}

export function ResearchPanel({ sessionId }: Props) {
  const [status, setStatus] = useState<string>("planning");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [reportMd, setReportMd] = useState<string | null>(null);
  const [citationsValid, setCitationsValid] = useState<boolean | null>(null);
  const [lowConfidence, setLowConfidence] = useState<boolean | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [reportLoading, setReportLoading] = useState(false);
  const [highlightN, setHighlightN] = useState<number | null>(null);
  const itemRefs = useRef<(HTMLDivElement | null)[]>([]);
  const esRef = useRef<EventSource | null>(null);

  // Reset state and open a fresh EventSource whenever sessionId changes.
  useEffect(() => {
    // React 18 batches all of these into a single re-render.
    /* eslint-disable react-hooks/set-state-in-effect */
    setStatus("planning");
    setStreamError(null);
    setReportMd(null);
    setCitationsValid(null);
    setLowConfidence(null);
    setEvidence([]);
    setReportLoading(false);
    setHighlightN(null);
    /* eslint-enable react-hooks/set-state-in-effect */
    itemRefs.current = [];

    let terminalReceived = false;
    let cancelled = false;
    let reconnectAttempted = false;

    function connect() {
      const es = openResearchStream(sessionId);
      esRef.current = es;

      es.onmessage = (e: MessageEvent) => {
        if (cancelled) return;
        const data = JSON.parse(e.data as string) as {
          status: string;
          error?: string;
        };
        setStatus(data.status);

        if (TERMINAL.has(data.status)) {
          terminalReceived = true;
          es.close();

          if (data.status === "failed") {
            setStreamError(data.error ?? "Run failed");
            return;
          }

          // status === "done": fetch report + evidence
          setReportLoading(true);
          Promise.all([getResearch(sessionId), getEvidence(sessionId)])
            .then(([res, evs]) => {
              if (cancelled) return;
              const md = res.report_md ?? null;
              setReportMd(md);
              setCitationsValid(res.citations_valid ?? null);
              setLowConfidence(res.low_confidence ?? null);
              setEvidence(md ? buildCitedEvidence(md, evs) : evs);
            })
            .catch(() => { if (!cancelled) setStreamError("Failed to load report"); })
            .finally(() => { if (!cancelled) setReportLoading(false); });
        }
      };

      es.onerror = () => {
        if (cancelled) return;
        es.close();
        if (!terminalReceived && !reconnectAttempted) {
          // Access token may have expired — try refreshing then reconnecting once.
          reconnectAttempted = true;
          refreshTokens().then((ok) => {
            if (ok && !cancelled) connect();
            else if (!cancelled) setStreamError("Stream connection lost");
          });
        } else if (!terminalReceived) {
          setStreamError("Stream connection lost");
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      esRef.current?.close();
      esRef.current = null;
    };
  }, [sessionId]);

  // Scroll the clicked citation into view and flash-highlight it.
  function handleCiteClick(n: number) {
    setHighlightN(n);
    itemRefs.current[n - 1]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setTimeout(() => setHighlightN(null), 1500);
  }

  const isDone = status === "done";
  const isFailed = status === "failed";

  return (
    <div className="space-y-4">
      {/* 5.3 — Live progress timeline (hidden once done) */}
      {!isDone && !isFailed && <ProgressTimeline status={status} />}

      {/* Failed state */}
      {isFailed && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3.5 text-sm text-rose-700">
          <span className="font-semibold">Run failed</span>
          {streamError ? ` — ${streamError}` : ""}
        </div>
      )}

      {/* Loading report after stream closes */}
      {isDone && reportLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <svg className="h-4 w-4 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading report…
        </div>
      )}

      {/* 5.4 + 5.5 — Report + evidence side-panel */}
      {isDone && !reportLoading && reportMd && (
        <div className="grid grid-cols-[1fr_22rem] items-start gap-4">
          {/* Report (5.4) */}
          <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
            <div className="mb-5 flex flex-wrap items-center gap-2 border-b border-slate-100 pb-4">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Report
              </h2>
              {citationsValid === true && (
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                  ✓ citations valid
                </span>
              )}
              {lowConfidence && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                  ⚠ low confidence
                </span>
              )}
            </div>

            <div className="space-y-3 text-sm leading-relaxed text-slate-700">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => (
                    <h1 className="mb-3 mt-1 text-xl font-bold text-slate-900">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="mb-2 mt-5 text-base font-semibold text-slate-900">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="mb-1 mt-4 text-sm font-semibold text-slate-800">{children}</h3>
                  ),
                  p: ({ children }) => (
                    <p className="leading-relaxed">
                      {transformCitations(children, handleCiteClick)}
                    </p>
                  ),
                  li: ({ children }) => (
                    <li className="ml-4 list-disc leading-relaxed">
                      {transformCitations(children, handleCiteClick)}
                    </li>
                  ),
                  ul: ({ children }) => <ul className="space-y-1">{children}</ul>,
                  ol: ({ children }) => (
                    <ol className="list-decimal space-y-1 pl-4">{children}</ol>
                  ),
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className="text-slate-600 underline hover:text-slate-900"
                    >
                      {children}
                    </a>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-slate-200 pl-3 text-slate-500 italic">
                      {children}
                    </blockquote>
                  ),
                  code: ({ children }) => (
                    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">
                      {children}
                    </code>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse text-xs">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border border-slate-200 bg-slate-50 px-3 py-1.5 text-left font-medium">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-slate-200 px-3 py-1.5">{children}</td>
                  ),
                  hr: () => <hr className="border-slate-200" />,
                }}
              >
                {reportMd}
              </ReactMarkdown>
            </div>
          </div>

          {/* Evidence inspector (5.5) */}
          <EvidencePanel
            evidence={evidence}
            highlightN={highlightN}
            itemRefs={itemRefs}
          />
        </div>
      )}
    </div>
  );
}
