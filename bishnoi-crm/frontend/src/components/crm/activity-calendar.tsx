import Link from "next/link";
import { Icon } from "@/src/platform/ui/icons";
import type { ActivityItem } from "@/src/platform/lib/types";
import { customerOf, dayOf } from "./follow-up-rows";
import { kindOf } from "./words";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
// More than this on a day, and the rest are counted, not listed.
const PER_DAY = 4;

/** The first and the day after the last of a month ("2026-10"), as YYYY-MM-DD. */
export function monthRange(month: string): { from: string; to: string } {
  const [y, m] = month.split("-").map(Number);
  const next = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
  return { from: `${month}-01`, to: `${next}-01` };
}

/** Every day shown for a month: whole weeks, Monday first, so the grid has no holes. */
function gridDays(month: string): string[] {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1));
  const start = new Date(first);
  start.setUTCDate(1 - ((first.getUTCDay() + 6) % 7));
  const last = new Date(Date.UTC(y, m, 0));
  const end = new Date(last);
  end.setUTCDate(last.getUTCDate() + (6 - ((last.getUTCDay() + 6) % 7)));
  const days = [];
  for (const d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1)) days.push(d.toISOString().slice(0, 10));
  return days;
}

/**
 * A month of activities, a day to a box: what's due or was done that day,
 * in the company's own days. Overdue reads red, done reads quiet; each links to
 * its customer.
 */
export function ActivityCalendar({ items, month, today, timeZone, showOwner }: { items: ActivityItem[]; month: string; today: string; timeZone: string; showOwner: boolean }) {
  const byDay = new Map<string, ActivityItem[]>();
  for (const a of items) {
    const day = dayOf(a.at, timeZone);
    byDay.set(day, [...(byDay.get(day) ?? []), a]);
  }
  const time = new Intl.DateTimeFormat("en-PH", { timeZone, hour: "numeric", minute: "2-digit" });

  function entry(a: ActivityItem) {
    const customer = customerOf(a);
    const tone = a.isDone ? "text-ink-3 line-through decoration-ink-3/50" : a.isOverdue ? "text-danger" : "text-ink";
    const label = `${time.format(new Date(a.at))} ${kindOf(a.kind).label}: ${a.subject}${customer.name ? ` (${customer.name})` : ""}${showOwner ? ` · ${a.owner.name}` : ""}${a.isDone ? ", done" : a.isOverdue ? ", overdue" : ""}`;
    const body = (
      <>
        <Icon name={kindOf(a.kind).icon} className="size-3 shrink-0" />
        <span className="truncate">
          {a.isPlanned && <span className="tabular-nums">{time.format(new Date(a.at))} </span>}
          {a.subject}
        </span>
      </>
    );
    return (
      <li key={a.id} title={label} className={a.meetingLink && !a.isDone ? "flex items-center gap-1" : undefined}>
        {a.meetingLink && !a.isDone && (
          <a href={a.meetingLink} target="_blank" rel="noopener noreferrer" aria-label={`Join: ${a.subject}`} className="order-last shrink-0 rounded-md bg-ink px-1.5 py-0.5 text-[0.6875rem] font-medium text-white hover:bg-hema-hover">
            Join
          </a>
        )}
        {customer.href ? (
          <Link href={customer.href} aria-label={label} className={`flex items-center gap-1 rounded-md px-1 py-0.5 text-[0.75rem] leading-tight hover:bg-bench ${tone}`}>
            {body}
          </Link>
        ) : (
          <span aria-label={label} className={`flex items-center gap-1 px-1 py-0.5 text-[0.75rem] leading-tight ${tone}`}>
            {body}
          </span>
        )}
      </li>
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className="grid min-w-[46rem] grid-cols-7 border-t border-l border-rule">
        {WEEKDAYS.map((d) => (
          <div key={d} className="border-r border-b border-rule bg-bench/60 px-2 py-1.5 text-caps font-semibold text-ink-3 uppercase">
            {d}
          </div>
        ))}
        {gridDays(month).map((day) => {
          const inMonth = day.startsWith(month);
          const list = byDay.get(day) ?? [];
          return (
            <div key={day} className={`min-h-28 border-r border-b border-rule px-1.5 py-1 ${inMonth ? "bg-sheet" : "bg-bench/40"}`}>
              <p
                className={`mb-1 text-meta ${
                  day === today ? "inline-flex size-6 items-center justify-center rounded-full bg-hema font-semibold text-white" : inMonth ? "text-ink-2" : "text-ink-3"
                }`}
              >
                {Number(day.slice(8))}
              </p>
              <ul className="space-y-0.5">{list.slice(0, PER_DAY).map(entry)}</ul>
              {list.length > PER_DAY && (
                <details className="text-[0.75rem]">
                  <summary className="cursor-pointer px-1 text-ink-3 hover:text-ink">{list.length - PER_DAY} more</summary>
                  <ul className="space-y-0.5">{list.slice(PER_DAY).map(entry)}</ul>
                </details>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
