import { useState } from "react";
import { DocumentUploadForm } from "./components/DocumentUploadForm";
import { HealthBadge } from "./components/HealthBadge";
import { QuestionForm } from "./components/QuestionForm";
import { ResearchPanel } from "./components/ResearchPanel";
import { RunHistory } from "./components/RunHistory";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";

function AppInner() {
  const { user, loading, logout } = useAuth();
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  // Avoid flashing the login page while the /auth/me check is in flight.
  if (loading) return null;
  if (!user) return <LoginPage />;

  function handleSubmitted(id: number) {
    setSelectedSessionId(id);
    setHistoryRefreshKey((k) => k + 1);
  }

  return (
    <div className="flex h-screen flex-col">
      {/* ── Header ── */}
      <header className="flex-none border-b border-slate-800 bg-slate-900">
        <div className="mx-auto flex max-w-screen-xl items-center justify-between px-6 py-3.5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-sm">
              {/* research / document icon */}
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M9 4.804A7.968 7.968 0 0 0 5.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 0 1 5.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0 1 14.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0 0 14.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 1 1-2 0V4.804z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white">
                Autonomous Research Analyst
              </h1>
              <p className="text-[11px] text-slate-400">
                Multi-agent · RAG · Cited reports
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-slate-400">{user.email}</span>
            <button
              onClick={() => void logout()}
              className="rounded-md px-2.5 py-1 text-xs text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
            >
              Sign out
            </button>
            <HealthBadge />
          </div>
        </div>
      </header>

      {/* ── Body: sidebar + main ── */}
      <div className="mx-auto flex w-full max-w-screen-xl flex-1 overflow-hidden">
        <RunHistory
          selectedSessionId={selectedSessionId}
          onSelect={setSelectedSessionId}
          refreshKey={historyRefreshKey}
        />

        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <div className="space-y-5 p-6">
            {/* Question form card */}
            <div className="rounded-xl bg-white px-6 py-5 shadow-sm ring-1 ring-slate-200">
              <QuestionForm onSubmitted={handleSubmitted} />
            </div>

            {/* Document upload (collapsible) */}
            <DocumentUploadForm />

            {/* Research panel — mounted once a session is selected */}
            {selectedSessionId !== null && (
              <ResearchPanel sessionId={selectedSessionId} />
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
