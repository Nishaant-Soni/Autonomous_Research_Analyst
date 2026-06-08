import { useEffect, useState } from "react";
import { fetchHealth } from "../lib/api";

type HealthState = "checking" | "ok" | "down";

// A small badge in the page header that confirms the React app can actually reach the
// FastAPI backend. Mostly here to prove out CORS + VITE_API_URL plumbing during Group A;
// stays useful as a deployment sanity check.
export function HealthBadge() {
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let active = true;
    fetchHealth()
      .then(() => active && setState("ok"))
      .catch(() => active && setState("down"));
    return () => {
      active = false;
    };
  }, []);

  const styles =
    state === "ok"
      ? "bg-emerald-100 text-emerald-700 border-emerald-200"
      : state === "down"
        ? "bg-rose-100 text-rose-700 border-rose-200"
        : "bg-slate-100 text-slate-600 border-slate-200";
  const label =
    state === "ok" ? "API connected" : state === "down" ? "API unreachable" : "Checking API…";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          state === "ok"
            ? "bg-emerald-500"
            : state === "down"
              ? "bg-rose-500"
              : "bg-slate-400"
        }`}
      />
      {label}
    </span>
  );
}
