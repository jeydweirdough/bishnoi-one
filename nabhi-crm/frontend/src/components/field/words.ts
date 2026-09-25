import { can } from "@/src/platform/lib/access";
import type { Me } from "@/src/platform/lib/types";
import type { FieldCounts, VisitOutcome } from "./types";

/** A field agent: logs visits, doesn't quote, doesn't watch others. Their location is required. */
export const isFieldAgent = (me: Me) => can(me, "visits.create") && !can(me, "quotes.view") && !can(me, "goals.view");

// How field work is said on screen. Not a client module, so server pages can use it too.

export const OUTCOMES: { value: VisitOutcome; label: string; past: string }[] = [
  { value: "collected", label: "Collected", past: "Collected a payment" },
  { value: "promised", label: "Promised to pay", past: "Promised to pay" },
  { value: "not_in", label: "Not in", past: "Doctor not in" },
  { value: "updated", label: "Updated details", past: "Updated their details" },
  { value: "other", label: "Other", past: "Visited" },
];

export const outcomeOf = (value: VisitOutcome) => OUTCOMES.find((o) => o.value === value) ?? OUTCOMES[OUTCOMES.length - 1];

/** The four goals, in the order they're shown. `money`: counted in centavos. */
export const MEASURES: { key: keyof FieldCounts; label: string; money?: boolean }[] = [
  { key: "doctorsVisited", label: "Doctors visited" },
  { key: "doctorsUpdated", label: "Doctors updated" },
  { key: "amountCentavos", label: "Amount collected", money: true },
  { key: "collectionVisits", label: "Collection visits" },
];

/** The month before or after "2026-09". */
export function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + by, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** How far along a goal is, 0–100, or null when there's no goal. */
export function progress(actual: number, goal: number | undefined | null): number | null {
  if (!goal) return null;
  return Math.min(100, Math.round((actual / goal) * 100));
}
