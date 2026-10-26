import { ArrowDownRight, ArrowUpRight, Search } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

// The list layout every module's main lists share (decided 2026-10-25, after the user's reference:
// a clinic Sales page): one white frame holding two or three headline figures with their change on
// last month, underline tabs, one toolbar row (search left; period and export right), then a table
// whose rows open in place (ExpandableTable). Few choices at the top (Hick's law), each control by
// what it acts on (proximity), details where you are (no page load). One accent: actions only.

/** The frame the list sits in: a white panel with a light border, nothing nested inside it. */
export function ListFrame({ children }: { children: ReactNode }) {
  return <section className="overflow-hidden rounded-2xl border border-rule bg-white">{children}</section>;
}

export type Figure = { label: string; value: string; icon?: ReactNode; change?: { text: string; tone: "up" | "down" | "flat"; good?: "up" | "down" } };

/** Two or three headline figures, side by side with dividers, each with its change on last month. */
export function FigureStrip({ figures }: { figures: Figure[] }) {
  return (
    <div className="grid divide-y divide-rule border-b border-rule sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-3">
      {figures.map((f) => {
        // Up is good for sales and collections; a list can say down is good (overdue, DSO).
        const good = f.change && f.change.tone !== "flat" && f.change.tone === (f.change.good ?? "up");
        const tone = !f.change || f.change.tone === "flat" ? "text-ink-3" : good ? "text-sage-deep" : "text-danger";
        return (
          <div key={f.label} className="flex items-center gap-3 px-5 py-4">
            {f.icon && <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-mint text-sage-deep">{f.icon}</span>}
            <div className="min-w-0">
              <p className="text-meta text-ink-3">{f.label}</p>
              <p className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-xl font-semibold tracking-[-0.01em] text-ink tabular-nums">{f.value}</span>
                {f.change && (
                  <span className={`inline-flex items-center gap-0.5 text-meta font-medium ${tone}`}>
                    {f.change.tone === "up" ? <ArrowUpRight className="size-3.5" aria-hidden /> : f.change.tone === "down" ? <ArrowDownRight className="size-3.5" aria-hidden /> : null}
                    {f.change.text}
                  </span>
                )}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export type Tab = { href: string; label: string; count?: number; current: boolean };

/** Underline tabs: what the list shows. A count beside a tab says how many are in it. */
export function UnderlineTabs({ tabs, label = "Show" }: { tabs: Tab[]; label?: string }) {
  return (
    <nav aria-label={label} className="flex gap-6 overflow-x-auto border-b border-rule px-5">
      {tabs.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={t.current ? "page" : undefined}
          className={`-mb-px shrink-0 border-b-2 py-3 text-sm ${t.current ? "border-sage-deep font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}
        >
          {t.label}
          {t.count ? <span className={`ml-1.5 rounded-full px-1.5 text-meta tabular-nums ${t.current ? "bg-mint-2 text-sage-deep" : "bg-bench text-ink-3"}`}>{t.count}</span> : null}
        </Link>
      ))}
    </nav>
  );
}

/** One row of tools: search on the left (a GET form, keeping the other filters), anything else on the right. */
export function ListToolbar({ q, placeholder, keep = {}, children }: { q: string; placeholder: string; keep?: Record<string, string>; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
      <form className="relative w-full max-w-xs">
        {Object.entries(keep).map(([k, v]) => (v ? <input suppressHydrationWarning key={k} type="hidden" name={k} value={v} /> : null))}
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
        <input
          suppressHydrationWarning
          name="q"
          defaultValue={q}
          placeholder={placeholder}
          aria-label={placeholder}
          className="h-9 w-full rounded-xl border border-rule bg-bench pr-3 pl-9 text-sm outline-none focus:border-sage-deep focus:bg-white"
        />
      </form>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export type PillTone = "good" | "warn" | "bad" | "info" | "plain";

const PILL: Record<PillTone, string> = {
  good: "bg-mint-2 text-sage-deep",
  warn: "bg-[#fff4e0] text-[#8a5a00]",
  bad: "bg-danger-tint text-danger",
  info: "bg-[#eef2fb] text-[#3b5bb5]",
  plain: "bg-bench text-ink-2",
};

/** A status, as a soft pill: read at a glance by colour, said in words. */
export function StatusPill({ tone, children }: { tone: PillTone; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.6875rem] font-semibold tracking-[0.02em] uppercase ${PILL[tone]}`}>{children}</span>;
}
