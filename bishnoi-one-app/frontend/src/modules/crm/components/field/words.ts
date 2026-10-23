import { can } from "@/src/modules/crm/lib/access";
import type { Me } from "@/src/platform/lib/types";
import type { CareGroup, FieldCounts, Reaction, VisitOutcome, Zone } from "@/src/modules/crm/components/field/types";

/** A field agent: logs visits, doesn't quote, doesn't watch others. Their location is required. */
export const isFieldAgent = (me: Me) => can(me, "visits.create") && !can(me, "quotes.view") && !can(me, "goals.view");

// How field work is said on screen. Not a client module, so server pages can use it too.

export const OUTCOMES: { value: VisitOutcome; label: string; past: string }[] = [
  { value: "detailed", label: "Product detailing", past: "Product detailing" },
  { value: "collected", label: "Payment collected", past: "Payment collected" },
  { value: "promised", label: "Payment promised", past: "Payment promised" },
  { value: "not_in", label: "Unavailable", past: "Unavailable" },
  { value: "updated", label: "Details updated", past: "Details updated" },
  { value: "other", label: "Other", past: "Visited" },
];

/** How a doctor took a product that was detailed, best first; `tone` colours it. */
export const REACTIONS: { value: Reaction; label: string; tone: "good" | "plain" | "bad" }[] = [
  { value: "will_prescribe", label: "Will prescribe", tone: "good" },
  { value: "already_prescribes", label: "Already prescribes", tone: "good" },
  { value: "interested", label: "Interested", tone: "plain" },
  { value: "neutral", label: "Neutral", tone: "plain" },
  { value: "concerns", label: "Has concerns", tone: "bad" },
  { value: "not_interested", label: "Not interested", tone: "bad" },
];

export const reactionOf = (value: Reaction) => REACTIONS.find((r) => r.value === value) ?? REACTIONS[3];

export const outcomeOf = (value: VisitOutcome) => OUTCOMES.find((o) => o.value === value) ?? OUTCOMES[OUTCOMES.length - 1];

/** The four goals, in the order they're shown. `money`: counted in centavos. */
export const MEASURES: { key: keyof FieldCounts; label: string; money?: boolean }[] = [
  { key: "doctorsVisited", label: "Accounts visited" },
  { key: "doctorsUpdated", label: "Accounts updated" },
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

/** The zones a week is routed by (Rx playbook), in the order a day visits them. */
export const ZONES: { value: Zone; label: string; when: string; dot: string; pill: string }[] = [
  { value: "red", label: "Red", when: "Patients ready: visit in the morning", dot: "bg-[#e34948]", pill: "bg-[#e34948]/12 text-[#b42318]" },
  { value: "yellow", label: "Yellow", when: "Lapsed: recover them midday", dot: "bg-[#eda100]", pill: "bg-[#eda100]/15 text-[#8a5a00]" },
  { value: "green", label: "Green", when: "Stable: an afternoon visit to keep in touch", dot: "bg-[#1a8a52]", pill: "bg-[#1a8a52]/12 text-[#1a6b40]" },
];

/** Visits a month each tier needs (as app/routers/field.py TIER_VISITS). */
export const TIER_VISITS = { 1: 4, 2: 2, 3: 1 } as const;

/** What was done about the doctor's Patient Care Group on a visit (Rx playbook). */
export const CARE_GROUP: { value: CareGroup; label: string; past: string }[] = [
  { value: "enrolled", label: "Enrolled", past: "Enrolled in Patient Care Group" },
  { value: "followed_up", label: "Followed up", past: "Patient Care Group follow-up" },
  { value: "not_now", label: "Not enrolled", past: "" },
];
