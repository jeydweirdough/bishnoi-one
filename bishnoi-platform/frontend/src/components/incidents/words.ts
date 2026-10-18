import type { Incident } from "@/src/lib/types";
import { ago } from "@/src/lib/words";

// How the incident screens say who an incident reaches and how long it ran.

/** Naming no companies means everyone on its application, or everyone at all. */
export function reach(i: Pick<Incident, "companies" | "application">): string {
  if (i.companies.length > 0) return i.companies.map((c) => c.name).join(", ");
  return i.application ? `All users of ${i.application.name}` : "All users";
}

/** "40 min", "3 h 10 min", "2 d 4 h". */
export function span(fromIso: string, toIso: string | null, now = Date.now()): string {
  const minutes = Math.max(0, Math.round(((toIso ? Date.parse(toIso) : now) - Date.parse(fromIso)) / 60_000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  return hours % 24 ? `${Math.floor(hours / 24)} d ${hours % 24} h` : `${Math.floor(hours / 24)} d`;
}

/** "Started 2 h ago", or "Lasted 3 h 10 min" once it's over. */
export function howLong(i: Pick<Incident, "startedAt" | "resolvedAt">): string {
  return i.resolvedAt ? `Lasted ${span(i.startedAt, i.resolvedAt)}` : `Started ${ago(i.startedAt)}`;
}
