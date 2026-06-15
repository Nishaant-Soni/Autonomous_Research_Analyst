import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  getEvidence,
  getResearch,
  openResearchStream,
  type EvidenceItem,
} from "../lib/api";
import { refreshTokens } from "../lib/authFetch";

const STAGES = [
  { key: "planning", label: "Planning", body: "Framing the investigation" },
  { key: "researching", label: "Researching", body: "Gathering corpus and web evidence" },
  { key: "critiquing", label: "Critiquing", body: "Testing groundedness and coverage" },
  { key: "writing", label: "Writing", body: "Synthesizing a report draft" },
  { key: "validating", label: "Validating", body: "Checking citations and report consistency" },
  { key: "done", label: "Done", body: "Report ready for review" },
];

const TERMINAL = new Set(["done", "failed"]);

function formatSourcesBlock(reportMd: string): string {
  const marker = "\n## Sources\n";
  const start = reportMd.indexOf(marker);
  if (start === -1) return reportMd;

  const body = reportMd.slice(0, start + marker.length);
  const sources = reportMd.slice(start + marker.length).trim();
  if (!sources) return reportMd;

  const rewritten = sources
    .replace(/\s+(?=\[\d+\]\s)/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join("\n\n");

  return `${body}${rewritten}`;
}

function buildCitedEvidence(reportMd: string, all: EvidenceItem[]): EvidenceItem[] {
  const sourcesMatch = reportMd.match(/^##\s*Sources\s*\n([\s\S]*)$/im);
  if (!sourcesMatch) return all;

  const cited: EvidenceItem[] = [];
  for (const line of sourcesMatch[1].split("\n")) {
    const match = line.match(/^\[(\d+)\]\s+(.+)$/);
    if (!match) continue;
    const ref = match[2].trim();
    let found: EvidenceItem | undefined;
    if (ref.startsWith("chunk #")) {
      const chunkId = parseInt(ref.slice(7), 10);
      found = all.find((item) => item.source_chunk_id === chunkId);
    } else {
      found = all.find((item) => item.source_url === ref);
    }
    if (found) cited.push(found);
  }
  return cited.length > 0 ? cited : all;
}

function transformCitations(
  children: React.ReactNode,
  onClick: (n: number) => void,
): React.ReactNode {
  return React.Children.map(children, (child) => {
    if (typeof child !== "string") return child;
    const parts = child.split(/(\[\d+\])/g);
    if (parts.length === 1) return child;
    return parts.map((part, i) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (!match) return part;
      const n = parseInt(match[1], 10);
      return (
        <button
          key={i}
          type="button"
          onClick={() => onClick(n)}
          className="mx-0.5 inline-flex rounded-full border border-cyan-300/20 bg-cyan-400/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-cyan-100 transition hover:border-cyan-300/30 hover:bg-cyan-400/20"
        >
          {part}
        </button>
      );
    });
  });
}

function ProgressTimeline({ status }: { status: string }) {
  const currentIdx = STAGES.findIndex((stage) => stage.key === status);

  return (
    <section className="panel overflow-hidden">
      <div className="border-b border-white/10 px-6 py-5">
        <p className="eyebrow">Live run status</p>
        <div className="mt-2 flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-white">Investigation in progress</h2>
            <p className="mt-2 text-sm leading-7 text-slate-400">
              The graph updates every stage as it plans, retrieves, critiques, writes, and
              validates the final report.
            </p>
          </div>
          <div className="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-4 py-2 text-xs font-medium text-cyan-100">
            Current phase: {status}
          </div>
        </div>
      </div>

      <div className="grid gap-3 px-4 py-4 md:grid-cols-2 xl:grid-cols-6">
        {STAGES.map((stage, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <div
              key={stage.key}
              className={`rounded-[24px] border p-4 transition duration-200 ${
                active
                  ? "border-cyan-300/30 bg-cyan-400/10 shadow-[0_18px_36px_rgba(6,182,212,0.1)]"
                  : done
                    ? "border-emerald-300/20 bg-emerald-400/10"
                    : "border-white/8 bg-white/[0.03]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-2xl text-sm font-semibold ${
                    active
                      ? "bg-cyan-300/20 text-cyan-100"
                      : done
                        ? "bg-emerald-300/20 text-emerald-100"
                        : "bg-white/8 text-slate-400"
                  }`}
                >
                  {done ? "✓" : i + 1}
                </div>
                {active && <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-cyan-300" />}
              </div>
              <p className="mt-4 text-sm font-semibold text-white">{stage.label}</p>
              <p className="mt-2 text-xs leading-6 text-slate-400">{stage.body}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  highlightN: number | null;
  itemRefs: React.MutableRefObject<(HTMLDivElement | null)[]>;
}

function EvidencePanel({ evidence, highlightN, itemRefs }: EvidencePanelProps) {
  return (
    <aside className="panel h-full overflow-hidden">
      <div className="border-b border-white/10 px-5 py-5">
        <h2 className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">
          Evidence
        </h2>
        <p className="mt-1 text-[11px] text-slate-500">
          Click a citation in the report to highlight it here.
        </p>
      </div>

      <div className="max-h-[68vh] divide-y divide-white/5 overflow-y-auto scrollbar-thin">
        {evidence.length === 0 && (
          <div className="px-5 py-10 text-center">
            <p className="text-sm font-medium text-slate-300">No evidence available yet</p>
            <p className="mt-2 text-xs leading-6 text-slate-500">
              Once the report is complete, cited web and corpus evidence will appear here.
            </p>
          </div>
        )}

        {evidence.map((item, i) => (
          <div
            key={i}
            ref={(el) => {
              itemRefs.current[i] = el;
            }}
            className={`px-4 py-3 transition duration-300 ${
              highlightN === i + 1 ? "bg-cyan-400/10" : "hover:bg-white/[0.03]"
            }`}
          >
            <div className="flex items-start gap-2.5">
              <span
                className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-2xl font-mono text-[10px] font-semibold ${
                  highlightN === i + 1
                    ? "bg-cyan-300/20 text-cyan-100"
                    : "bg-white/8 text-slate-300"
                }`}
              >
                [{i + 1}]
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`status-pill ring-1 ${
                      item.retriever === "web"
                        ? "bg-sky-400/12 text-sky-200 ring-sky-400/20"
                        : "bg-violet-400/12 text-violet-200 ring-violet-400/20"
                    }`}
                  >
                    {item.retriever}
                  </span>
                  {item.source_chunk_id != null && !item.source_url && (
                    <span className="text-[11px] text-slate-500">chunk #{item.source_chunk_id}</span>
                  )}
                </div>

                {item.claim && (
                  <p
                    className="mt-2 overflow-hidden text-xs font-medium leading-5 text-slate-100"
                    style={{
                      display: "-webkit-box",
                      WebkitBoxOrient: "vertical",
                      WebkitLineClamp: 2,
                    }}
                  >
                    {item.claim}
                  </p>
                )}

                <p
                  className="mt-2 overflow-hidden text-[11px] leading-6 text-slate-400"
                  style={{
                    display: "-webkit-box",
                    WebkitBoxOrient: "vertical",
                    WebkitLineClamp: 3,
                  }}
                >
                  {item.content}
                </p>

                {item.source_url && (
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 block truncate text-[10px] text-cyan-200 transition hover:text-cyan-100 hover:underline"
                  >
                    {item.source_url}
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

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

  useEffect(() => {
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
            .catch(() => {
              if (!cancelled) setStreamError("Failed to load report");
            })
            .finally(() => {
              if (!cancelled) setReportLoading(false);
            });
        }
      };

      es.onerror = () => {
        if (cancelled) return;
        es.close();
        if (!terminalReceived && !reconnectAttempted) {
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

  function handleCiteClick(n: number) {
    setHighlightN(n);
    itemRefs.current[n - 1]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setTimeout(() => setHighlightN(null), 1500);
  }

  const isDone = status === "done";
  const isFailed = status === "failed";

  return (
    <div className="space-y-5">
      <section className="panel overflow-hidden">
        <div className="border-b border-white/10 px-6 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="eyebrow">Selected run</p>
              <h1 className="mt-2 text-3xl font-semibold text-white">Research report</h1>
              <p className="mt-2 text-sm leading-7 text-slate-400">
                Stream the run live, then inspect the completed report and citation-backed source
                material in one place.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="status-pill bg-cyan-400/12 text-cyan-100 ring-1 ring-cyan-300/20">
                {status}
              </span>
              {citationsValid === true && (
                <span className="status-pill bg-emerald-400/12 text-emerald-100 ring-1 ring-emerald-300/20">
                  citations valid
                </span>
              )}
              {lowConfidence && (
                <span className="status-pill bg-amber-400/12 text-amber-100 ring-1 ring-amber-300/20">
                  low confidence
                </span>
              )}
            </div>
          </div>
        </div>

        {streamError && !isFailed && (
          <div className="border-b border-rose-400/10 bg-rose-500/10 px-6 py-3 text-sm text-rose-200">
            {streamError}
          </div>
        )}

        {!isDone && !isFailed && <ProgressTimeline status={status} />}

        {isFailed && (
          <div className="px-6 py-8">
            <div className="rounded-[24px] border border-rose-400/20 bg-rose-500/10 px-5 py-5">
              <p className="text-lg font-semibold text-rose-100">Run failed</p>
              <p className="mt-2 text-sm leading-7 text-rose-200/85">
                {streamError ?? "The research run ended unexpectedly."}
              </p>
            </div>
          </div>
        )}

        {isDone && reportLoading && (
          <div className="flex items-center gap-3 px-6 py-8 text-sm text-slate-300">
            <svg className="h-4 w-4 animate-spin text-cyan-300" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading completed report...
          </div>
        )}
      </section>

      {isDone && !reportLoading && reportMd && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.18fr)_18.2rem]">
          <section className="panel overflow-hidden">
            <div className="border-b border-white/10 px-6 py-5">
              <p className="eyebrow">Final output</p>
              <h2 className="mt-2 text-2xl font-semibold text-white">Validated report</h2>
              <p className="mt-2 text-sm leading-7 text-slate-400">
                Review the finished brief below. Numbered citations on the page map directly to the
                evidence rail on the right.
              </p>
            </div>

            <div className="px-6 py-6">
              <div className="space-y-4 text-[15px] leading-8 text-slate-300">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({ children }) => (
                      <h1 className="headline-serif mb-5 text-4xl leading-tight text-white">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="mt-8 border-t border-white/8 pt-6 text-xl font-semibold text-white">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="mt-6 text-base font-semibold text-slate-100">{children}</h3>
                    ),
                    p: ({ children }) => (
                      <p className="leading-8 text-slate-300">
                        {transformCitations(children, handleCiteClick)}
                      </p>
                    ),
                    li: ({ children }) => (
                      <li className="ml-5 list-disc leading-8 text-slate-300">
                        {transformCitations(children, handleCiteClick)}
                      </li>
                    ),
                    ul: ({ children }) => <ul className="space-y-2">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal space-y-2 pl-5">{children}</ol>,
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noreferrer"
                        className="text-cyan-200 underline decoration-cyan-300/40 underline-offset-4 transition hover:text-cyan-100"
                      >
                        {children}
                      </a>
                    ),
                    blockquote: ({ children }) => (
                      <blockquote className="rounded-r-2xl border-l-2 border-cyan-300/35 bg-cyan-400/5 px-4 py-3 italic text-slate-300">
                        {children}
                      </blockquote>
                    ),
                    code: ({ children }) => (
                      <code className="rounded-lg bg-white/8 px-1.5 py-1 font-mono text-xs text-cyan-100">
                        {children}
                      </code>
                    ),
                    table: ({ children }) => (
                      <div className="overflow-x-auto rounded-2xl border border-white/8">
                        <table className="w-full border-collapse text-sm">{children}</table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th className="border-b border-white/8 bg-white/[0.04] px-4 py-3 text-left font-medium text-slate-100">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="border-b border-white/5 px-4 py-3 text-slate-300">{children}</td>
                    ),
                    hr: () => <hr className="border-white/10" />,
                  }}
                >
                  {formatSourcesBlock(reportMd)}
                </ReactMarkdown>
              </div>
            </div>
          </section>

          <EvidencePanel evidence={evidence} highlightN={highlightN} itemRefs={itemRefs} />
        </div>
      )}
    </div>
  );
}
