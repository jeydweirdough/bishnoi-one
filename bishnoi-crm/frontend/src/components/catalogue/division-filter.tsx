import Link from "next/link";
import type { DivisionOption } from "@/src/platform/lib/types";

/** For someone over several divisions: one division's promos or bundles at a time. */
export function DivisionFilter({ base, teams, current }: { base: string; teams: DivisionOption[]; current: string }) {
  if (teams.length < 2) return null;
  const options = [{ id: "", name: "Every division" }, ...teams];
  return (
    <nav aria-label="Division" className="mb-3 flex flex-wrap gap-1.5">
      {options.map((t) => (
        <Link
          key={t.id}
          href={t.id ? `${base}?division=${t.id}` : base}
          scroll={false}
          aria-current={t.id === current ? "true" : undefined}
          className={`rounded-md border px-2.5 py-0.5 text-meta ${t.id === current ? "border-hema bg-hema-tint font-semibold text-ink" : "border-rule-strong text-ink-2 hover:text-ink"}`}
        >
          {t.name}
        </Link>
      ))}
    </nav>
  );
}

/** The rows for one division, or every row. */
export function inDivision<T extends { teamIds: string[] }>(rows: T[], division: string): T[] {
  return division ? rows.filter((r) => r.teamIds.includes(division)) : rows;
}
