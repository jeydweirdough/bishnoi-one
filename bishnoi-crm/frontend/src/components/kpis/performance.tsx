import Link from "next/link";
import type { Format } from "@/src/platform/lib/format";
import type { KpiDef, KpiResult, KpiScorecard, KpiStatus } from "@/src/platform/lib/types";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { FigureCard, LeadFigure, Tile, type Figure } from "@/src/platform/ui/figures";
import { STATUS, kpiValue } from "./words";

// Performance: what each person's month is measured by, against its target.
// The same cards as the dashboard and Deals: the result large, what it is,
// then where it stands against the target.

const PILL_TONE = { green: "good", amber: "warn", red: "bad", none: "plain", waiting: "plain" } as const;

/** One measure's result as a figure card. */
export function resultFigure(kpi: KpiDef, r: KpiResult, fmt: Format, href?: string): Figure {
  const s = STATUS[r.status];
  const byToday = r.target && r.expected !== null && r.expected !== r.target && kpi.better === "higher" ? ` · ${kpiValue(kpi.unit, r.expected, fmt)} by today` : "";
  return {
    value: kpiValue(kpi.unit, r.actual, fmt),
    label: kpi.name,
    note: r.target !== null ? `of ${kpiValue(kpi.unit, r.target, fmt)}${byToday}${kpi.better === "lower" ? " · lower is better" : ""}` : "No target set",
    ring: r.target !== null ? r.attainment : null,
    pill: r.target !== null ? { text: s.label, tone: PILL_TONE[r.status] } : undefined,
    href,
  };
}

/** Where a set of results stands: on target, slightly behind, behind, without a target. */
export function tally(results: KpiResult[]) {
  const n = (s: KpiStatus) => results.filter((r) => r.status === s).length;
  return { green: n("green"), amber: n("amber"), red: n("red"), none: results.filter((r) => r.target === null).length };
}

/** The four status cards on top of a performance page. */
export function StatusFigures({ results, targetsHref }: { results: KpiResult[]; targetsHref?: string }) {
  const t = tally(results);
  const targeted = results.length - t.none;
  const figures: Figure[] = [
    { value: String(t.green), label: "On target", note: targeted ? `of ${targeted} with a target` : "No targets set", ring: targeted ? Math.round((100 * t.green) / targeted) : null },
    { value: String(t.amber), label: "Slightly behind", note: targeted ? "Near expected pace" : "—" },
    { value: String(t.red), label: "Behind", note: t.red ? "Below expected pace" : "None behind", alert: t.red > 0 },
    { value: String(t.none), label: "Without a target", note: t.none ? (targetsHref ? "Set under Targets" : "Set by your team lead") : "All results have targets", href: t.none ? targetsHref : undefined },
  ];
  return (
    <div className="mb-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {figures.map((f, i) => (
        <FigureCard key={f.label} figure={f} first={i === 0} />
      ))}
    </div>
  );
}

/**
 * A salesperson's month, one card: what they're measured by leads (the
 * figure large, where it stands, the ring); everything else is a row under it,
 * so the eye has one place to start.
 */
export function YourMonth({ card, more, fmt, month }: { card: KpiScorecard | null; more: Figure[]; fmt: Format; month: string }) {
  const results = card?.people[0]?.results ?? {};
  const measured = (card?.kpis ?? []).filter((k) => results[k.id]);
  const figures = [...measured.map((k) => resultFigure(k, results[k.id], fmt, "/performance")), ...more];
  if (!figures.length) return null;
  const [lead, ...rest] = figures;
  return (
    <MonthCard
      title="Monthly performance"
      subtitle={`${fmt.monthLabel(card?.month ?? month)} to date`}
      action={measured.length > 0 ? { href: "/performance", label: "View performance" } : undefined}
      lead={lead}
      rest={rest}
    />
  );
}

/**
 * A month on a home page, one card: the figure the month is judged by leads,
 * in its own block (large, where it stands, its ring); the rest are tiles
 * under it. Every home uses it, so the eye always starts in the same place.
 */
export function MonthCard({ title, subtitle, action, lead, rest }: { title: string; subtitle: string; action?: { href: string; label: string }; lead: Figure; rest: Figure[] }) {
  return (
    <Sheet className="flex-1 px-5 pt-4 pb-5">
      {/* The same heading as the card beside it, so the two line up. */}
      <SectionTitle
        icon="goals"
        action={
          action && (
            <Link href={action.href} className="text-meta font-medium text-ink hover:underline">
              {action.label}
            </Link>
          )
        }
      >
        {title}
      </SectionTitle>
      <p className="text-meta text-ink-3">{subtitle}</p>
      <div className="mt-3">
        <LeadFigure figure={lead} />
      </div>
      {rest.length > 0 && (
        <div className="mt-3 grid auto-rows-fr grid-cols-2 gap-3">
          {rest.map((f) => (
            <Tile key={f.label} figure={f} />
          ))}
        </div>
      )}
    </Sheet>
  );
}

/** How far along something is against a target by today: the ring, the pill (met, on pace, slightly behind, behind) and the note. */
export function paceFigure({
  value,
  label,
  actual,
  target,
  start,
  end,
  today,
  show,
  href,
  noTarget = "No target set",
}: {
  value: string;
  label: string;
  actual: number;
  target: number | null | undefined;
  start: string;
  end: string;
  today: string;
  show: (n: number) => string;
  href?: string;
  noTarget?: string;
}): Figure {
  if (!target) return { value, label, note: noTarget, href };
  const day = (key: string) => Date.parse(`${key}T00:00:00Z`);
  const span = day(end) - day(start);
  const share = span > 0 ? Math.min(1, Math.max(0, (day(today) - day(start) + 86_400_000) / span)) : 1;
  const pace = Math.round(target * share);
  const pill =
    actual >= target
      ? { text: "Target met", tone: "good" as const }
      : actual >= pace
        ? { text: "On pace", tone: "good" as const }
        : actual >= pace * 0.8
          ? { text: "Slightly behind", tone: "warn" as const }
          : { text: "Behind", tone: "bad" as const };
  return { value, label, note: `of ${show(target)}${actual < target ? ` · ${show(pace)} by today` : ""}`, ring: Math.round((100 * actual) / target), pill, href };
}

