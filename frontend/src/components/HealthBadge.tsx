import { useEffect, useState } from "react";
import { fetchHealth } from "../lib/api";

type HealthState = "checking" | "ok" | "down";

export function HealthBadge() {
  const [state, setState] = useState<HealthState>("checking");

  useEffect(() => {
    let active = true;
    fetchHealth()
      .then(() => active && setState("ok"))
      .catch(() => active && setState("down"));
    return () => { active = false; };
  }, []);

  const styles =
    state === "ok"
      ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20"
      : state === "down"
        ? "bg-rose-500/10 text-rose-400 ring-rose-500/20"
        : "bg-slate-500/10 text-slate-400 ring-slate-500/20";

  const label =
    state === "ok" ? "API connected" : state === "down" ? "API unreachable" : "Checking…";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${styles}`}>
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          state === "ok"
            ? "animate-pulse bg-emerald-400"
            : state === "down"
              ? "bg-rose-400"
              : "bg-slate-400"
        }`}
      />
      {label}
    </span>
  );
}
