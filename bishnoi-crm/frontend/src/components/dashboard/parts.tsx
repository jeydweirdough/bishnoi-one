import { ArrowDown, ArrowRight, ArrowUp, CircleCheck, Lightbulb, TrendingDown, TrendingUp, TriangleAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, type IconName } from "@/src/platform/ui/icons";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { Bone } from "@/src/platform/ui/skeleton";
import type { Figure } from "../deals/figure-card";
import { FollowUpItem, type FollowUpRow } from "../follow-up-item";
import type { Org } from "@/src/platform/lib/types";
import { Amount, Amounts } from "@/src/platform/ui/amount";

/** How many items a dashboard list shows before "and N more". */
export const LIST_ROWS = 4;

/** A tab's list of meetings and tasks: the first few, then how many more and where they are. */
export function DueList({ rows, today, org, empty, more }: { rows: FollowUpRow[]; today: string; org: Org; empty: string; more?: string }) {
  if (rows.length === 0) return <p className="py-3 text-meta text-ink-3">{empty}</p>;
  return (
    <>
      <ul className="divide-y divide-rule">
        {rows.slice(0, LIST_ROWS).map((f) => (
          <FollowUpItem key={f.id} today={today} row={f} org={org} />
        ))}
      </ul>
      {more && (
        <p className="border-t border-rule pt-2.5 text-meta text-ink-3">
          And {rows.length - LIST_ROWS} more.{" "}
          <Link href={more} className="font-medium text-ink underline-offset-4 hover:underline">
            See all
          </Link>
        </p>
      )}
    </>
  );
}

// The pieces every role's Home dashboard is drawn with, so a salesperson's, a
// team lead's and a field agent's read the same way: an overview of four
// figures, each against something; cards with the CRM's own section titles;
// a line under a chart saying what it shows. Each has a waiting version drawn
// with its own label, so the dashboard is laid out before its figures land.

/** A card's link on the right of its title: where the whole list is. */
export function CardLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="inline-flex shrink-0 items-center gap-1 rounded text-meta font-medium text-ink underline-offset-4 hover:underline">
      {children}
      <ArrowRight className="size-3.5" aria-hidden />
    </Link>
  );
}

/** One figure of an overview. `note` says how it compares; `pill` where it stands, in words. */
export type Stat = { icon: IconName; label: string; value: string; note: ReactNode; pill?: Figure["pill"]; href?: string };

/**
 * Where a figure stands, as an icon after it rather than a word chip: three
 * states read at a glance, each its own shape as well as colour (so it reads
 * without colour too). The words stay for screen readers and on hover.
 */
function standing(pill: NonNullable<Figure["pill"]>): { Icon: LucideIcon; tone: string } {
  if (pill.tone === "bad") return { Icon: TrendingDown, tone: "text-danger" };
  if (pill.tone === "warn") return { Icon: TriangleAlert, tone: "text-[#b7791f]" };
  if (/pace/i.test(pill.text)) return { Icon: TrendingUp, tone: "text-filed" };
  return { Icon: CircleCheck, tone: "text-filed" };
}

function StatBody({ icon, label, value, note, pill }: Omit<Stat, "href">) {
  const mark = pill ? standing(pill) : null;
  return (
    <div className="flex items-start gap-3.5 px-5 py-4">
      <span className="grid size-10 shrink-0 place-items-center rounded-full bg-mint text-sage-deep" aria-hidden>
        <Icon name={icon} className="size-[1.125rem]" />
      </span>
      <div className="min-w-0">
        <p className="text-meta font-medium text-ink-2">{label}</p>
        <p className="mt-0.5 flex min-w-0 items-center gap-2">
          <span className="truncate text-[1.5rem] leading-tight font-semibold tracking-[-0.015em] text-ink tabular-nums"><Amount text={value} /></span>
          {mark && pill && (
            <span className={`inline-flex shrink-0 ${mark.tone}`} title={pill.text}>
              <mark.Icon className="size-5" strokeWidth={2.25} aria-hidden />
              <span className="sr-only">{pill.text}</span>
            </span>
          )}
        </p>
        <div className="mt-1 text-meta text-ink-3">{typeof note === "string" ? <Amounts text={note} /> : note}</div>
      </div>
    </div>
  );
}

/** How the month stands: four figures in one card, divided, each a link to where it comes from. */
export function Overview({ title = "Overview", action, stats }: { title?: string; action?: ReactNode; stats: Stat[] }) {
  return (
    <Sheet className="mb-5 pt-4 pb-2">
      <div className="px-5">
        <SectionTitle icon="overview" action={action}>
          {title}
        </SectionTitle>
      </div>
      <div className="mt-2 grid sm:grid-cols-2 xl:grid-cols-4 xl:divide-x xl:divide-rule">
        {stats.map(({ href, ...s }) =>
          href ? (
            <Link key={s.label} href={href} className="block rounded-lg transition-colors duration-150 hover:bg-bench focus-visible:bg-bench">
              <StatBody {...s} />
            </Link>
          ) : (
            <StatBody key={s.label} {...s} />
          ),
        )}
      </div>
    </Sheet>
  );
}

/** The overview as it waits: the same card, each figure's label drawn, its number to come. */
export function OverviewLoading({ title = "Overview", stats }: { title?: string; stats: { icon: IconName; label: string }[] }) {
  return (
    <Sheet className="mb-5 pt-4 pb-2">
      <div className="px-5">
        <SectionTitle icon="overview">{title}</SectionTitle>
      </div>
      <div className="mt-2 grid sm:grid-cols-2 xl:grid-cols-4 xl:divide-x xl:divide-rule">
        {stats.map((s) => (
          <div key={s.label} className="flex items-start gap-3.5 px-5 py-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-mint text-sage-deep" aria-hidden>
              <Icon name={s.icon} className="size-[1.125rem]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-meta font-medium text-ink-2">{s.label}</p>
              <Bone className="mt-2 h-6 w-28" />
              <Bone className="mt-2.5 h-3 w-32" />
            </div>
          </div>
        ))}
      </div>
    </Sheet>
  );
}

/** Up or down on last month, an arrow and the share; nothing last month says so. */
export function Change({ now, before }: { now: number; before: number | undefined }) {
  if (!before) return <>Nothing last month</>;
  const pct = Math.round((100 * (now - before)) / before);
  const Arrow = pct >= 0 ? ArrowUp : ArrowDown;
  return (
    <span className="inline-flex items-center gap-1">
      <Arrow className={`size-3.5 ${pct >= 0 ? "text-filed" : "text-danger"}`} aria-hidden />
      <span>
        {Math.abs(pct)}% {pct >= 0 ? "up" : "down"} on last month
      </span>
    </span>
  );
}

/**
 * A share as a large ring with the figure in the middle (customers kept).
 * With nothing to compare yet it shows the count instead of an empty ring.
 */
export function ShareRing({ pct, label, sub, count }: { pct: number | null; label: string; sub: string; count?: number }) {
  const filled = Math.max(0, Math.min(100, pct ?? 0));
  return (
    <figure className="relative mx-auto size-36 shrink-0" aria-label={pct === null ? `${count ?? 0} ${sub}` : `${pct}% ${label}, ${sub}`}>
      <svg viewBox="0 0 44 44" className="size-full -rotate-90" aria-hidden>
        <circle cx="22" cy="22" r="18" fill="none" stroke="var(--color-mint-2)" strokeWidth="3.5" />
        {pct !== null && filled > 0 && (
          <circle cx="22" cy="22" r="18" fill="none" stroke="var(--color-sage-deep)" strokeWidth="3.5" strokeLinecap="round" strokeDasharray={`${(filled / 100) * 113.1} 113.1`} />
        )}
      </svg>
      <figcaption className="absolute inset-0 flex flex-col items-center justify-center px-4 text-center" aria-hidden>
        <span className="text-[1.75rem] leading-none font-semibold tracking-[-0.02em] text-ink tabular-nums">{pct === null ? (count ?? 0) : `${pct}%`}</span>
        <span className="mt-1.5 text-meta font-medium text-ink">{pct === null ? "Customers" : label}</span>
        <span className="text-[0.6875rem] leading-snug text-ink-3">{sub}</span>
      </figcaption>
    </figure>
  );
}

/** One line under a chart saying what it shows, in the mint of the CRM's good news. */
export function Insight({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 flex items-start gap-2.5 rounded-lg bg-mint px-4 py-3 text-meta leading-relaxed text-ink">
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-sage-deep" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

/** A sub-section inside a card, sentence case: "Customer health". */
export function PartTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-1 flex min-h-6 items-center justify-between gap-3">
      <h3 className="text-sm font-semibold text-ink">{children}</h3>
      {action}
    </div>
  );
}

/** Quoting over the months, said in a sentence: this month against the last, and the best month. */
export function quotedInsight(points: { month: string; quotedCentavos: number }[], fmt: { peso: (n: number) => string; pesoCompact: (n: number) => string; monthLabel: (m: string) => string }, who = "Your"): string | null {
  if (points.length < 2) return null;
  const [before, now] = points.slice(-2);
  const best = points.reduce((a, b) => (b.quotedCentavos > a.quotedCentavos ? b : a));
  let text: string;
  if (!before.quotedCentavos && !now.quotedCentavos) text = "Nothing quoted in the last two months. A quote a week keeps customers coming back.";
  else if (!before.quotedCentavos) text = `${fmt.peso(now.quotedCentavos)} quoted so far this month, after nothing last month.`;
  else {
    const pct = Math.round((100 * (now.quotedCentavos - before.quotedCentavos)) / before.quotedCentavos);
    text =
      pct >= 0
        ? `${fmt.peso(now.quotedCentavos)} quoted so far this month, already ${pct}% more than all of last month.`
        : `${fmt.peso(now.quotedCentavos)} quoted so far this month, ${Math.abs(pct)}% short of last month's ${fmt.peso(before.quotedCentavos)}.`;
  }
  if (best.quotedCentavos > 0 && best.month !== now.month) text += ` ${who} best month was ${fmt.monthLabel(best.month)}, at ${fmt.pesoCompact(best.quotedCentavos)}.`;
  return text;
}
