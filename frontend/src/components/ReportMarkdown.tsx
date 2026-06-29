import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders the validated report markdown.
 *
 * Security: report text incorporates content gathered from the web and user-uploaded
 * documents, so it is partially attacker-influenced. This component is the single render
 * path for it, and it is intentionally safe:
 *  - no `rehype-raw` plugin, so embedded raw HTML (e.g. `<script>`) is escaped, not executed;
 *  - no `dangerouslySetInnerHTML` anywhere;
 *  - react-markdown's default `urlTransform` strips dangerous link schemes (`javascript:` …);
 *  - links open with `rel="noreferrer"`.
 * `ReportMarkdown.test.tsx` locks this contract so a future change (e.g. adding rehype-raw)
 * can't silently reintroduce XSS.
 */

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

interface Props {
  reportMd: string;
  onCiteClick: (n: number) => void;
}

export function ReportMarkdown({ reportMd, onCiteClick }: Props) {
  return (
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
            {transformCitations(children, onCiteClick)}
          </p>
        ),
        li: ({ children }) => (
          <li className="ml-5 list-disc leading-8 text-slate-300">
            {transformCitations(children, onCiteClick)}
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
  );
}
