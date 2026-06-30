import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { errorMessageFromBody } from "../lib/api";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const BENEFITS = [
  "Blend private documents with live web retrieval.",
  "Trace every report sentence back to inspectable evidence.",
  "Review live investigation progress before the final report lands.",
];

export function LoginPage() {
  const { login } = useAuth();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(next: "signin" | "signup") {
    setMode(next);
    setError(null);
    setConfirm("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (mode === "signup" && password !== confirm) {
      setError("Passwords do not match");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "signup") {
        const res = await fetch(`${API_URL}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(errorMessageFromBody(body, "Registration failed"));
        }
        await login(email, password);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12 sm:px-6">
      <div className="absolute inset-0 bg-grid opacity-30" />
      <div className="absolute left-[-10%] top-[-5%] h-[28rem] w-[28rem] rounded-full bg-cyan-400/15 blur-3xl" />
      <div className="absolute bottom-[-10%] right-[-8%] h-[24rem] w-[24rem] rounded-full bg-violet-500/15 blur-3xl" />

      <div className="relative grid w-full max-w-6xl gap-6 xl:grid-cols-[1.1fr_28rem]">
        <section className="panel-strong overflow-hidden px-7 py-8 sm:px-10 sm:py-10">
          <div className="space-y-8">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-cyan-300/20 bg-gradient-to-br from-cyan-400/20 via-sky-500/20 to-violet-500/20 text-cyan-100 shadow-[0_12px_30px_rgba(6,182,212,0.18)]">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
                  <path d="M9 4.804A7.968 7.968 0 0 0 5.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 0 1 5.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0 1 14.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0 0 14.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 1 1-2 0V4.804z" />
                </svg>
              </div>
              <div>
                <p className="eyebrow">Autonomous Research Analyst</p>
                <p className="mt-1 text-sm text-slate-400">Professional multi-agent research workspace</p>
              </div>
            </div>

            <div className="max-w-3xl">
              <h1 className="headline-serif text-5xl leading-[0.92] text-white sm:text-6xl">
                Build citation-backed research deliverables with confidence.
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-8 text-slate-300">
                A polished analyst console for teams that want grounded synthesis, live investigation
                status, and evidence they can audit line by line.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {BENEFITS.map((item, index) => (
                <div key={item} className="panel-muted p-4">
                  <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-2xl bg-cyan-400/10 text-sm font-semibold text-cyan-200">
                    0{index + 1}
                  </div>
                  <p className="text-sm leading-7 text-slate-300">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="panel px-6 py-7 sm:px-7">
          <div className="mb-6">
            <p className="eyebrow">{mode === "signin" ? "Welcome back" : "Create access"}</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">
              {mode === "signin" ? "Sign in to continue" : "Create your account"}
            </h2>
            <p className="mt-2 text-sm leading-7 text-slate-400">
              Use your workspace credentials to access research sessions, uploaded documents, and
              citation-backed reports.
            </p>
          </div>

          <div className="mb-6 flex rounded-2xl border border-white/10 bg-white/[0.04] p-1">
            {(["signin", "signup"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => switchMode(item)}
                className={`flex-1 rounded-[18px] px-3 py-2 text-sm font-medium transition ${
                  mode === item
                    ? "bg-white/10 text-white shadow-[0_8px_22px_rgba(0,0,0,0.18)]"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {item === "signin" ? "Sign in" : "Sign up"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                className="field"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-200">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="field"
                placeholder="Enter your password"
              />
            </div>

            {mode === "signup" && (
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-200">
                  Confirm password
                </label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  className="field"
                  placeholder="Repeat your password"
                />
              </div>
            )}

            {error && (
              <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            )}

            <button type="submit" disabled={submitting} className="button-primary w-full">
              {submitting ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {mode === "signin" ? "Signing in..." : "Creating account..."}
                </>
              ) : (
                <>{mode === "signin" ? "Sign in" : "Create account"}</>
              )}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
