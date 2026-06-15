import { useState } from "react";
import { ApiError, postResearch } from "../lib/api";

interface Props {
  onSubmitted: (sessionId: number) => void;
}

export function QuestionForm({ onSubmitted }: Props) {
  const [question, setQuestion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = question.trim();
  const canSubmit = trimmed.length > 0 && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const { session_id } = await postResearch(trimmed);
      onSubmitted(session_id);
      setQuestion("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `API ${err.status}: ${err.message}`
          : err instanceof Error
            ? err.message
            : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3.5">
      <div>
        <p className="eyebrow">Start a new run</p>
        <h3 className="mt-2 text-2xl font-semibold text-white">Draft the research brief</h3>
        <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-400">
          Ask one focused question and the system will return a cited report with inspectable
          evidence.
        </p>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-200">Research question</label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          className="textarea-field"
          placeholder="Example: Compare how top teams evaluate retrieval quality for internal research copilots. Include concrete metrics, failure modes, and what is practical to instrument in production."
          disabled={submitting}
        />
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="flex justify-end border-t border-white/10 pt-3.5">
        <button type="submit" disabled={!canSubmit} className="button-primary">
          {submitting ? (
            <>
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Launching run...
            </>
          ) : (
            <>
              Start research
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path fillRule="evenodd" d="M11.72 4.22a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06l3.72-3.72H3a.75.75 0 0 1 0-1.5h12.44l-3.72-3.72a.75.75 0 0 1 0-1.06z" clipRule="evenodd" />
              </svg>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
