import { useState } from "react";
import { DocumentUploadForm } from "./components/DocumentUploadForm";
import { HealthBadge } from "./components/HealthBadge";
import { QuestionForm } from "./components/QuestionForm";
import { ResearchPanel } from "./components/ResearchPanel";
import { RunHistory } from "./components/RunHistory";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";

const HIGHLIGHTS = [
  { label: "Agents", value: "5-node graph" },
  { label: "Grounding", value: "RAG + live web" },
  { label: "Output", value: "Cited markdown" },
];

function AppInner() {
  const { user, loading, logout } = useAuth();
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  if (loading) return null;
  if (!user) return <LoginPage />;

  function handleSubmitted(id: number) {
    setSelectedSessionId(id);
    setHistoryRefreshKey((k) => k + 1);
  }

  return (
    <div className="app-shell">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/55 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-300/20 bg-gradient-to-br from-cyan-400/20 via-sky-500/20 to-violet-500/20 text-cyan-100 shadow-[0_12px_30px_rgba(6,182,212,0.18)]">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                <path d="M9 4.804A7.968 7.968 0 0 0 5.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 0 1 5.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0 1 14.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0 0 14.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 1 1-2 0V4.804z" />
              </svg>
            </div>
            <div>
              <p className="eyebrow">Autonomous Research Workspace</p>
              <h1 className="headline-serif mt-1 text-3xl leading-none text-white sm:text-[2.15rem]">
                Analyst Console
              </h1>
            </div>
          </div>

          <div className="flex flex-col gap-3 lg:items-end">
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <HealthBadge />
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[11px] font-medium text-slate-300">
                {user.email}
              </span>
              <button onClick={() => void logout()} className="button-secondary">
                Sign out
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {HIGHLIGHTS.map((item) => (
                <div key={item.label} className="panel-muted px-3 py-2">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
                    {item.label}
                  </p>
                  <p className="mt-1 text-xs font-medium text-slate-200">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px] flex-col gap-5 px-4 py-5 sm:px-6 lg:flex-row lg:px-8">
        <RunHistory
          selectedSessionId={selectedSessionId}
          onSelect={setSelectedSessionId}
          onNewResearch={() => setSelectedSessionId(null)}
          refreshKey={historyRefreshKey}
        />

        <main className="min-w-0 flex-1 overflow-y-auto scrollbar-thin">
          <div className="space-y-5 pb-8">
            {selectedSessionId === null ? (
              <div className="space-y-5">
                <section className="panel-strong px-6 py-4 sm:px-7 sm:py-5">
                  <QuestionForm onSubmitted={handleSubmitted} />
                </section>

                <section className="panel px-6 py-5">
                  <div className="space-y-4">
                    <div>
                      <p className="eyebrow">Workspace prep</p>
                      <h3 className="mt-2 text-xl font-semibold text-white">
                        Prime the run with internal material
                      </h3>
                      <p className="mt-2 text-sm leading-7 text-slate-400">
                        Drop in technical notes, strategy memos, PDFs, or markdown so the graph can
                        retrieve them during synthesis.
                      </p>
                    </div>
                    <DocumentUploadForm />
                  </div>
                </section>
              </div>
            ) : (
              <ResearchPanel key={selectedSessionId} sessionId={selectedSessionId} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
