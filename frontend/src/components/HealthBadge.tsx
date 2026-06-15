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
    return () => {
      active = false;
    };
  }, []);

  const styles =
    state === "ok"
      ? "bg-emerald-400/12 text-emerald-200 ring-emerald-400/20"
      : state === "down"
        ? "bg-rose-400/12 text-rose-200 ring-rose-400/20"
        : "bg-slate-400/10 text-slate-300 ring-white/10";

  const dot =
    state === "ok"
      ? "animate-pulse bg-emerald-300"
      : state === "down"
        ? "bg-rose-300"
        : "bg-slate-400";

  const label =
    state === "ok" ? "API connected" : state === "down" ? "API unreachable" : "Checking API";

  return (
    <span className={`status-pill ring-1 ${styles}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
