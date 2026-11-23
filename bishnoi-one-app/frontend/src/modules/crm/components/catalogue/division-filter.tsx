import { DivisionSelect } from "./division-select";
import type { DivisionOption } from "@/src/platform/lib/types";

/** For someone over several divisions: one division's promos or bundles at a time. */
export function DivisionFilter({ base, teams, current }: { base: string; teams: DivisionOption[]; current: string }) {
  if (teams.length < 2) return null;
  return <DivisionSelect base={base} teams={teams} current={current} />;
}

/** The rows for one division, or every row. */
export function inDivision<T extends { teamIds: string[] }>(rows: T[], division: string): T[] {
  return division ? rows.filter((r) => r.teamIds.includes(division)) : rows;
}

/** Promos or bundles with no division apply to nobody (pricing gives each division its own): said, with the first
 *  few named, so they're fixed (2026-11-23: imported ones came without divisions). */
export function NoDivisionNotice<T extends { teamIds: string[]; name: string }>({ rows, what }: { rows: T[]; what: "promo" | "bundle" }) {
  const none = rows.filter((r) => r.teamIds.length === 0);
  if (none.length === 0) return null;
  const shown = none.slice(0, 4).map((r) => r.name);
  return (
    <p role="status" className="mb-3 rounded-lg bg-promo-tint px-4 py-2 text-sm text-ink">
      {none.length} {what}
      {none.length === 1 ? " has" : "s have"} no division, so no quote or sales order can use {none.length === 1 ? "it" : "them"}: open{" "}
      {none.length === 1 ? "it" : "each"} and pick the divisions {none.length === 1 ? "it's" : "they're"} for.
      <span className="block text-meta text-ink-2">
        {shown.join(", ")}
        {none.length > shown.length ? ` and ${none.length - shown.length} more` : ""}.
      </span>
    </p>
  );
}
