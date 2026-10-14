import Link from "next/link";
import { Sheet } from "@/src/platform/ui/sheet";
import type { Coverage } from "./types";
import { ZONES } from "./words";

// The month against the plan (Rx playbook): how much of the list was visited
// at least once (below the goal, 80%, the month's score is capped), each tier
// against its visits a month, and how the list is zoned this week.

export function CoverageCard({ coverage, monthName, doctorsHref = "/field/doctors", many = "doctors" }: { coverage: Coverage; monthName: string; doctorsHref?: string; many?: string }) {
  const pct = coverage.coveragePct;
  const short = pct !== null && pct < coverage.goalPct;
  const left = Math.max(0, Math.ceil((coverage.goalPct / 100) * coverage.doctors) - coverage.visited);
  const zoned = (z: string) => `${doctorsHref}?zone=${z}`;
  return (
    <Sheet className="px-5 pt-4 pb-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-heading text-ink">Coverage</h2>
        <span className="text-meta text-ink-3">{monthName}</span>
      </div>
      {coverage.doctors === 0 ? (
        <p className="mt-2 text-sm text-ink-3">No {many} on your list yet.</p>
      ) : (
        <>
          <p className="mt-2 flex items-baseline gap-2">
            <span className={`text-[1.75rem] leading-tight font-semibold tabular-nums ${short ? "text-danger" : "text-filed"}`}>{pct}%</span>
            <span className="text-sm text-ink-2">
              of {coverage.doctors} {many} visited
            </span>
          </p>
          {/* The bar, with the goal marked on it. */}
          <span className="relative mt-2 block h-2.5 rounded-full bg-mint-2" role="img" aria-label={`${pct}% of the list visited; the goal is ${coverage.goalPct}%`}>
            <span className={`block h-full rounded-full ${short ? "bg-danger" : "bg-filed"}`} style={{ width: `${Math.min(100, pct ?? 0)}%` }} />
            <span className="absolute -top-1 h-4.5 w-0.5 rounded bg-ink" style={{ left: `calc(${coverage.goalPct}% - 1px)` }} aria-hidden />
          </span>
          <p className="mt-1.5 text-meta text-ink-3">
            {short
              ? `${left} more to reach ${coverage.goalPct}%. Below it, the month's score is capped.`
              : `At or above the ${coverage.goalPct}% goal.`}
          </p>

          <ul className="mt-4 space-y-1.5 text-sm">
            {coverage.tiers
              .filter((t) => t.doctors > 0)
              .map((t) => (
                <li key={t.tier} className="flex items-baseline justify-between gap-3">
                  <Link href={`${doctorsHref}?tier=${t.tier}`} className="text-ink-2 hover:text-ink hover:underline">
                    Tier {t.tier} <span className="text-meta text-ink-3">· {t.visitsNeeded}× a month</span>
                  </Link>
                  <span className="tabular-nums">
                    <span className="font-semibold text-ink">{t.onPlan}</span>
                    <span className="text-ink-3"> of {t.doctors} on plan</span>
                  </span>
                </li>
              ))}
            {coverage.untiered > 0 && (
              <li className="text-meta text-ink-3">
                {coverage.untiered} without a tier: <Link href={doctorsHref} className="text-ink underline-offset-2 hover:underline">give them one</Link>.
              </li>
            )}
          </ul>

          <div className="mt-4 flex flex-wrap gap-1.5">
            {ZONES.map((z) => (
              <Link key={z.value} href={zoned(z.value)} className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-meta font-semibold ${z.pill} hover:brightness-95`} title={z.when}>
                <span className={`size-1.5 rounded-full ${z.dot}`} aria-hidden />
                {z.label} · {coverage.zones[z.value]}
              </Link>
            ))}
            {coverage.zones.none > 0 && (
              <Link href={zoned("none")} className="inline-flex items-center rounded-full border border-dashed border-rule-strong px-2.5 py-1 text-meta text-ink-3 hover:text-ink">
                No zone · {coverage.zones.none}
              </Link>
            )}
          </div>
        </>
      )}
    </Sheet>
  );
}
