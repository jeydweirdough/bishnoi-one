"use client";

import Link from "next/link";
import { useState } from "react";
import type { AreaHealth, RenewalMonth } from "@/src/modules/admin/platform/lib/types";
import { adminPage } from "@/src/modules/admin/lib/page";

// The overview's two charts. Each answers one question:
// - Health: is each area current, and is it on target? Status colours (the
//   app's own filed / due-today / danger), always with an icon and a word.
// - Renewals by month: when does the renewal work pile up? One series, one
//   hue, with the overdue bucket first in the critical colour.

const GOOD = "var(--color-filed)";
const WARN = "var(--color-due-today)";
const BAD = "var(--color-danger)";
const BAR = "var(--color-due-later)";

/** The threshold: nothing overdue, and at most a quarter due soon. */
const DUE_SOON_LIMIT = 0.25;

type Status = { label: string; mark: string; color: string };
export function statusOf(a: { total: number; dueSoon: number; overdue: number }): Status {
  if (a.overdue > 0) return { label: "At risk", mark: "!", color: BAD };
  if (a.total > 0 && a.dueSoon / a.total > DUE_SOON_LIMIT) return { label: "Needs attention", mark: "•", color: WARN };
  return { label: "On track", mark: "✓", color: GOOD };
}

function StatusLabel({ status }: { status: Status }) {
  return (
    <span className="inline-flex items-center gap-1 text-meta font-semibold text-ink-2">
      <span aria-hidden className="inline-flex size-4 items-center justify-center rounded-full text-[0.625rem] leading-none text-white" style={{ background: status.color }}>
        {status.mark}
      </span>
      {status.label}
    </span>
  );
}

/** One 100% bar split into its parts, a 2px gap between them, with a hover note. */
function SplitBar({ parts, name }: { parts: { key: string; value: number; color: string; label: string }[]; name: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = parts.reduce((n, p) => n + p.value, 0);
  const shown = parts.filter((p) => p.value > 0);
  const note = shown.find((p) => p.key === hover);
  return (
    <div className="relative">
      <div className="flex h-3 w-full gap-0.5" role="img" aria-label={`${name}: ${shown.map((p) => `${p.value} ${p.label}`).join(", ") || "none"}`}>
        {total === 0 ? (
          <div className="h-full w-full rounded bg-bench" />
        ) : (
          shown.map((p, i) => (
            <div
              key={p.key}
              onMouseEnter={() => setHover(p.key)}
              onMouseLeave={() => setHover(null)}
              className={`h-full ${i === 0 ? "rounded-l" : ""} ${i === shown.length - 1 ? "rounded-r" : ""}`}
              style={{ width: `${(p.value / total) * 100}%`, background: p.color }}
            />
          ))
        )}
      </div>
      {note && (
        <div className="pointer-events-none absolute -top-8 left-0 z-10 rounded-[12px] bg-ink px-2 py-1 text-meta whitespace-nowrap text-white shadow-overlay">
          {note.value} {note.label} ({Math.round((note.value / total) * 100)}%)
        </div>
      )}
    </div>
  );
}

/** Each area's records: current, due soon, overdue, against the target. */
export function HealthChart({ areas, requests }: { areas: AreaHealth[]; requests: { open: number; late: number; onTime: number } }) {
  const requestStatus: Status = requests.late > 0 ? { label: "Past target date", mark: "!", color: BAD } : { label: "On time", mark: "✓", color: GOOD };
  return (
    <div>
      <ul className="space-y-4">
        {areas.map((a) => {
          const status = statusOf(a);
          return (
            <li key={a.key}>
              <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3">
                <Link href={adminPage(a.href)} className="text-sm font-semibold text-ink hover:text-hema hover:underline">
                  {a.label}
                </Link>
                <StatusLabel status={status} />
              </div>
              <SplitBar
                name={a.label}
                parts={[
                  { key: "current", value: a.current, color: GOOD, label: "current" },
                  { key: "soon", value: a.dueSoon, color: WARN, label: `due within ${a.windowDays} days` },
                  { key: "overdue", value: a.overdue, color: BAD, label: "overdue" },
                ]}
              />
              <p className="mt-1 text-meta text-ink-3 tabular-nums">
                {a.total === 0 ? "None recorded" : `${a.current} current · ${a.dueSoon} due within ${a.windowDays} days · ${a.overdue} overdue`}
              </p>
            </li>
          );
        })}
        <li>
          <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3">
            <Link href="/admin/tickets" className="text-sm font-semibold text-ink hover:text-hema hover:underline">
              Open office requests
            </Link>
            <StatusLabel status={requestStatus} />
          </div>
          <SplitBar
            name="Open office requests"
            parts={[
              { key: "ontime", value: requests.onTime, color: GOOD, label: "on time" },
              { key: "late", value: requests.late, color: BAD, label: "past target date" },
            ]}
          />
          <p className="mt-1 text-meta text-ink-3 tabular-nums">
            {requests.open === 0 ? "None open" : `${requests.onTime} on time · ${requests.late} past target date`}
          </p>
        </li>
      </ul>
      <p className="mt-4 border-t border-rule pt-2 text-meta text-ink-3">
        Target: nothing overdue, and no more than {DUE_SOON_LIMIT * 100}% of an area due for renewal at once.
      </p>
    </div>
  );
}

/** An area's records by how soon they're due, for its own page: current, due
 *  within its window, overdue. */
export function healthOf(days: (number | null | undefined)[], windowDays: number) {
  const dated = days.filter((d): d is number => d !== null && d !== undefined);
  const overdue = dated.filter((d) => d < 0).length;
  const dueSoon = dated.filter((d) => d >= 0 && d <= windowDays).length;
  return { total: dated.length, current: dated.length - overdue - dueSoon, dueSoon, overdue, windowDays };
}

/** The same bar as on the overview, at the top of an area's page. */
export function HealthStrip({ label, total, current, dueSoon, overdue, windowDays }: { label: string } & ReturnType<typeof healthOf>) {
  const status = statusOf({ total, dueSoon, overdue });
  return (
    <div className="mb-5 rounded-[12px] bg-sheet px-5 py-4 shadow-sheet">
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3">
        <p className="text-sm font-semibold text-ink">
          {total} {label}
        </p>
        <StatusLabel status={status} />
      </div>
      <SplitBar
        name={label}
        parts={[
          { key: "current", value: current, color: GOOD, label: "current" },
          { key: "soon", value: dueSoon, color: WARN, label: `due within ${windowDays} days` },
          { key: "overdue", value: overdue, color: BAD, label: "overdue" },
        ]}
      />
      <p className="mt-1 text-meta text-ink-3 tabular-nums">
        {current} current · {dueSoon} due within {windowDays} days · {overdue} overdue. Target: nothing overdue, no more than {DUE_SOON_LIMIT * 100}%
        due at once.
      </p>
    </div>
  );
}

/** Open office requests, on time or past their target date. */
export function RequestsStrip({ open, late, resolved }: { open: number; late: number; resolved: number }) {
  const status: Status = late > 0 ? { label: "Past target date", mark: "!", color: BAD } : { label: "On time", mark: "✓", color: GOOD };
  return (
    <div className="mb-5 rounded-[12px] bg-sheet px-5 py-4 shadow-sheet">
      <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-3">
        <p className="text-sm font-semibold text-ink">{open} open</p>
        <StatusLabel status={status} />
      </div>
      <SplitBar
        name="Open office requests"
        parts={[
          { key: "ontime", value: open - late, color: GOOD, label: "on time" },
          { key: "late", value: late, color: BAD, label: "past target date" },
        ]}
      />
      <p className="mt-1 text-meta text-ink-3 tabular-nums">
        {open - late} on time · {late} past target date · {resolved} resolved. Target: none past their target date.
      </p>
    </div>
  );
}

const AREAS = [
  { key: "permits", label: "Permits" },
  { key: "expatriates", label: "Expatriates" },
  { key: "documents", label: "Documents" },
  { key: "properties", label: "Leases" },
  { key: "vehicles", label: "Vehicles" },
] as const;

/** "Oct", and "Jan 2027" where the year turns, so a month never reads like a date. */
function monthLabel(m: string, i = 1, all: RenewalMonth[] = []): string {
  if (m === "overdue") return "Overdue";
  const at = new Date(`${m}-01T00:00:00`);
  const name = at.toLocaleDateString("en-PH", { month: "short" });
  const prev = all[i - 1]?.month;
  const newYear = prev && prev !== "overdue" && prev.slice(0, 4) !== m.slice(0, 4);
  return newYear ? `${name} ${m.slice(0, 4)}` : name;
}

/** How many renewals fall due each month, overdue first. */
export function RenewalsChart({ months }: { months: RenewalMonth[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const totals = months.map((m) => AREAS.reduce((n, a) => n + m[a.key], 0));
  const peak = Math.max(1, ...totals);
  // A readable scale: steps of 1, 2, 5 or 10 up to the tallest bar.
  const step = [1, 2, 5, 10, 20, 50].find((s) => peak / s <= 4) ?? 100;
  const top = Math.ceil(peak / step) * step;
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step);
  const H = 160;

  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button suppressHydrationWarning type="button" onClick={() => setAsTable(!asTable)} className="text-meta font-medium text-hema hover:underline">
          {asTable ? "Show chart" : "Show as table"}
        </button>
      </div>
      {asTable ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-1.5 font-semibold">Month</th>
              {AREAS.map((a) => (
                <th key={a.key} className="py-1.5 text-right font-semibold">
                  {a.label}
                </th>
              ))}
              <th className="py-1.5 text-right font-semibold">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule tabular-nums">
            {months.map((m, i) => (
              <tr key={m.month}>
                <td className="py-1.5">{monthLabel(m.month, i, months)}</td>
                {AREAS.map((a) => (
                  <td key={a.key} className="py-1.5 text-right">
                    {m[a.key]}
                  </td>
                ))}
                <td className="py-1.5 text-right font-semibold">{totals[i]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="flex gap-2">
          {/* The scale: recessive, left of the bars. */}
          <div className="relative w-6 shrink-0 text-right text-meta text-ink-3 tabular-nums" style={{ height: H }}>
            {ticks.map((t) => (
              <span key={t} className="absolute right-0 -translate-y-1/2" style={{ top: H - (t / top) * H }}>
                {t}
              </span>
            ))}
          </div>
          <div className="min-w-0 flex-1">
            <div className="relative" style={{ height: H }}>
              {ticks.map((t) => (
                <div key={t} className="absolute inset-x-0 border-t border-rule" style={{ top: H - (t / top) * H }} />
              ))}
              <div className="absolute inset-0 flex items-end gap-2">
                {months.map((m, i) => (
                  <div
                    key={m.month}
                    className="relative flex h-full flex-1 items-end justify-center"
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                  >
                    {totals[i] > 0 && (
                      <div
                        className="w-full max-w-10 rounded-t"
                        style={{ height: `${(totals[i] / top) * 100}%`, background: m.month === "overdue" ? BAD : BAR, opacity: hover === null || hover === i ? 1 : 0.55 }}
                      />
                    )}
                    {hover === i && (
                      <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 rounded-[12px] bg-ink px-2.5 py-1.5 text-meta whitespace-nowrap text-white shadow-overlay">
                        <p className="font-semibold">
                          {monthLabel(m.month, i, months)}: {totals[i]}
                        </p>
                        {AREAS.filter((a) => m[a.key] > 0).map((a) => (
                          <p key={a.key} className="tabular-nums">
                            {a.label} {m[a.key]}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-1.5 flex gap-2">
              {months.map((m, i) => (
                <span key={m.month} className={`flex-1 text-center text-meta ${m.month === "overdue" ? "font-semibold text-danger" : "text-ink-3"}`}>
                  {monthLabel(m.month, i, months)}
                  <span className="block font-semibold text-ink-2 tabular-nums">{totals[i]}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
