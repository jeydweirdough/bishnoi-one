import type { Check } from "@/src/lib/types";
import { ago } from "@/src/lib/words";

// How the Service screens say what a health check found.

/** "Answered in 120 ms · 3 min ago", or what went wrong and when. */
export function checkLine(check: Check | null | undefined, monitored: boolean): string {
  if (!monitored) return "No health address, so the platform can't ask it.";
  if (!check) return "Not asked yet.";
  const said = check.detail ?? (check.ms != null ? `Answered in ${check.ms} ms` : "Answered");
  return `${said.replace(/\.$/, "")} · ${ago(check.checkedAt)}`;
}

export const uptimeText = (uptime: number | null | undefined) => (uptime == null ? "—" : `${uptime}%`);

export const msText = (ms: number | null | undefined) => (ms == null ? "—" : `${ms.toLocaleString("en-PH")} ms`);
