import { useState } from "react";
import { DocumentUploadForm } from "./components/DocumentUploadForm";
import { HealthBadge } from "./components/HealthBadge";
import { QuestionForm } from "./components/QuestionForm";
import { RunHistory } from "./components/RunHistory";

// Layout: header + (sidebar | main).
// - Sidebar (plan 5.7): recent-runs list, polled every 3 s, click selects a session.
// - Main panel: question form + doc upload up top, and a placeholder for the selected
//   session. Group B replaces the placeholder with the SSE timeline + Markdown report +
//   side-panel evidence inspector.
export default function App() {
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  // Bumped on every new submit so the sidebar reloads immediately rather than waiting
  // for the next poll tick.
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  function handleSubmitted(id: number) {
    setSelectedSessionId(id);
    setHistoryRefreshKey((k) => k + 1);
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold text-slate-900">
            Autonomous Research Analyst
          </h1>
          <HealthBadge />
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-[18rem_1fr] gap-0 overflow-hidden">
        <RunHistory
          selectedSessionId={selectedSessionId}
          onSelect={setSelectedSessionId}
          refreshKey={historyRefreshKey}
        />

        <main className="space-y-6 overflow-y-auto p-6">
          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <QuestionForm onSubmitted={handleSubmitted} />
          </section>

          <DocumentUploadForm />

          {selectedSessionId !== null && (
            <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-medium text-slate-700">
                Selected session #{selectedSessionId}
              </h2>
              <p className="mt-3 text-xs text-slate-500">
                Live progress, the rendered report, and the evidence side-panel land in
                Phase 5 Group B. The session is being persisted in the meantime — see{" "}
                <code className="rounded bg-slate-100 px-1 py-px font-mono">
                  GET /research/{selectedSessionId}
                </code>{" "}
                for the current state.
              </p>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
