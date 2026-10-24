"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/src/platform/ui/icons";
import type { ActivityItem, CrmKind } from "@/src/platform/lib/types";
import { customerOf, dayOf } from "@/src/modules/crm/components/crm/follow-up-rows";
import { KINDS, kindOf } from "@/src/modules/crm/components/crm/words";

// The calendar in the UI kit's shape (decided 2026-10-22), on the CRM's own flow:
// Month or Week, filter by type (each with its colour and count), every call,
// meeting, email, note and task as a coloured entry linking to its customer.
// The week shows the hours, items that overlap side by side, and the time now.
// Clicking an empty day or hour plans a call there (New call, at that time).

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
// More than this on a day of the month, and the rest are counted, not listed.
const PER_DAY = 4;
// The week's hours, and how tall one is.
const FROM_HOUR = 7;
const TO_HOUR = 20;
const HOUR_PX = 52;

/** Each type's colour (the kit's tags, in our chart colours). */
export const KIND_COLOUR: Record<CrmKind, string> = {
  call: "#2a78d6",
  meeting: "#7a5cc4",
  email: "#eb6834",
  note: "#6a6a6a",
  task: "#1baf7a",
};



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

function weekDays(from: string): string[] {
  const d = new Date(`${from}T00:00:00Z`);
  return Array.from({ length: 7 }, (_, i) => {
    const x = new Date(d);
    x.setUTCDate(d.getUTCDate() + i);
    return x.toISOString().slice(0, 10);
  });
}

/** Asks New call (on this page) to open, planned for this moment. */
function planAt(day: string, hour: number) {
  window.dispatchEvent(new CustomEvent("bishnoi:new-call", { detail: { at: `${day}T${String(hour).padStart(2, "0")}:00` } }));
}

export type CalendarLinks = { previous: string; next: string; today: string | null; month: string; week: string };

export function ActivityCalendar({
  items,
  mode,
  month,
  weekFrom,
  title,
  today,
  timeZone,
  showOwner,
  canPlan,
  links,
}: {
  items: ActivityItem[];
  mode: "month" | "week";
  month: string;
  weekFrom: string;
  title: string;
  today: string;
  timeZone: string;
  showOwner: boolean;
  canPlan: boolean;
  links: CalendarLinks;
}) {
  const [hidden, setHidden] = useState<CrmKind[]>([]);
  const shown = items.filter((a) => !hidden.includes(a.kind));
  const counts = useMemo(() => Object.fromEntries(KINDS.map((k) => [k.kind, items.filter((a) => a.kind === k.kind).length])), [items]);
  const parts = useMemo(() => new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }), [timeZone]);
  const time = useMemo(() => new Intl.DateTimeFormat("en-PH", { timeZone, hour: "numeric", minute: "2-digit" }), [timeZone]);
  const byDay = new Map<string, ActivityItem[]>();
  for (const a of shown) {
    const day = dayOf(a.at, timeZone);
    byDay.set(day, [...(byDay.get(day) ?? []), a]);
  }
  const minutesOf = (a: ActivityItem) => {
    const [h, m] = parts.format(new Date(a.at)).split(":").map(Number);
    return h * 60 + m;
  };
  const labelOf = (a: ActivityItem) => {
    const customer = customerOf(a);
    return `${time.format(new Date(a.at))} ${kindOf(a.kind).label}: ${a.subject}${customer.name ? ` (${customer.name})` : ""}${showOwner ? ` · ${a.owner.name}` : ""}${a.isDone ? ", done" : a.isOverdue ? ", overdue" : ""}`;
  };

  function Entry({ a, block = false }: { a: ActivityItem; block?: boolean }) {
    const customer = customerOf(a);
    const c = KIND_COLOUR[a.kind];
    const body = (
      <>
        <Icon name={kindOf(a.kind).icon} className="size-3 shrink-0" />
        <span className={`min-w-0 ${block ? "line-clamp-2" : "truncate"} ${a.isDone ? "line-through decoration-current/40" : ""}`}>
          {a.isPlanned && <span className="tabular-nums">{time.format(new Date(a.at))} </span>}
          {a.subject}
          {block && customer.name && <span className="block truncate font-normal opacity-80">{customer.name}</span>}
        </span>
        {a.meetingLink && !a.isDone && (
          <a href={a.meetingLink} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} aria-label={`Join: ${a.subject}`} className="ml-auto shrink-0 rounded bg-ink px-1.5 py-px text-[0.625rem] font-medium text-white">
            Join
          </a>
        )}
      </>
    );
    const cls = `flex gap-1 rounded-md border-l-[3px] px-1.5 py-1 text-[0.72rem] leading-tight font-medium ${block ? "h-full items-start overflow-hidden" : "items-center"} ${a.isDone ? "opacity-55" : ""}`;
    const style = { borderColor: a.isOverdue && !a.isDone ? "#b42318" : c, background: `color-mix(in srgb, ${c} 11%, #ffffff)`, color: a.isOverdue && !a.isDone ? "#b42318" : "#141414" };
    return customer.href ? (
      <Link href={customer.href} title={labelOf(a)} aria-label={labelOf(a)} onClick={(e) => e.stopPropagation()} className={`${cls} hover:brightness-95`} style={style}>
        {body}
      </Link>
    ) : (
      <span title={labelOf(a)} aria-label={labelOf(a)} className={cls} style={style}>
        {body}
      </span>
    );
  }

  return (
    <div>
      {/* Where you are, and how to move */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-heading text-ink">{title}</h2>
        <div role="group" aria-label="View" className="inline-flex rounded-[9px] border border-rule bg-sheet p-0.5">
          {(["month", "week"] as const).map((m) => (
            <Link key={m} href={links[m]} aria-current={mode === m ? "page" : undefined} className={`rounded-[7px] px-3 py-1 text-meta font-medium ${mode === m ? "bg-ink text-white" : "text-ink-2 hover:text-ink"}`}>
              {m === "month" ? "Month" : "Week"}
            </Link>
          ))}
        </div>
        <div className="inline-flex items-center gap-1">
          <Link href={links.previous} aria-label={mode === "month" ? "Previous month" : "Previous week"} className="grid size-[34px] place-items-center rounded-[8px] border border-[#dededa] bg-sheet text-ink-2 hover:bg-[#f4f4f2]">
            <ChevronLeft className="size-4" aria-hidden />
          </Link>
          {links.today && (
            <Link href={links.today} className="inline-flex h-[34px] items-center rounded-[8px] border border-[#dededa] bg-sheet px-3 text-meta font-medium text-ink hover:bg-[#f4f4f2]">
              Today
            </Link>
          )}
          <Link href={links.next} aria-label={mode === "month" ? "Next month" : "Next week"} className="grid size-[34px] place-items-center rounded-[8px] border border-[#dededa] bg-sheet text-ink-2 hover:bg-[#f4f4f2]">
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        </div>
      </div>

      {/* Filter by type */}
      <div role="group" aria-label="Show types" className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-meta text-ink-3">Show</span>
        {KINDS.map((k) => {
          const on = !hidden.includes(k.kind);
          return (
            <button
              key={k.kind}
              type="button"
              aria-pressed={on}
              onClick={() => setHidden((h) => (on ? [...h, k.kind] : h.filter((x) => x !== k.kind)))}
              className={`inline-flex h-[30px] items-center gap-1.5 rounded-full border px-2.5 text-[0.78rem] font-medium transition-colors ${on ? "border-[#dededa] bg-sheet text-ink" : "border-dashed border-[#d6d6d4] bg-transparent text-ink-3"}`}
            >
              <i className="size-2 rounded-full" style={{ background: on ? KIND_COLOUR[k.kind] : "#d6d6d4" }} aria-hidden />
              {k.label}s
              <span className="tabular-nums text-ink-3">{counts[k.kind] ?? 0}</span>
            </button>
          );
        })}
        <span className="ml-auto text-meta text-ink-3">{shown.length === items.length ? `${items.length} in view` : `${shown.length} of ${items.length} shown`}</span>
      </div>

      {mode === "month" ? (
        <div className="overflow-x-auto rounded-[10px] border border-rule">
          <div className="grid min-w-[46rem] grid-cols-7">
            {WEEKDAYS.map((d) => (
              <div key={d} className="border-b border-rule bg-[#fbfbfa] px-2 py-2 text-caps font-semibold text-ink-3 uppercase">
                {d}
              </div>
            ))}
            {gridDays(month).map((day, i) => {
              const inMonth = day.startsWith(month);
              const list = byDay.get(day) ?? [];
              return (
                <div
                  key={day}
                  onClick={() => canPlan && planAt(day, 9)}
                  title={canPlan ? "Click to plan a call this day" : undefined}
                  className={`group min-h-28 border-b border-rule px-1.5 py-1 ${i % 7 ? "border-l" : ""} ${inMonth ? "bg-sheet" : "bg-[#fbfbfa]"} ${canPlan ? "cursor-pointer hover:bg-[#f7faf5]" : ""}`}
                >
                  <p className={`mb-1 text-meta ${day === today ? "inline-flex size-6 items-center justify-center rounded-full bg-ink font-semibold text-white" : inMonth ? "text-ink-2" : "text-ink-3"}`}>{Number(day.slice(8))}</p>
                  <ul className="space-y-0.5">
                    {list.slice(0, PER_DAY).map((a) => (
                      <li key={a.id}>
                        <Entry a={a} />
                      </li>
                    ))}
                  </ul>
                  {list.length > PER_DAY && (
                    <details className="text-[0.72rem]" onClick={(e) => e.stopPropagation()}>
                      <summary className="cursor-pointer px-1 text-ink-3 hover:text-ink">{list.length - PER_DAY} more</summary>
                      <ul className="space-y-0.5">
                        {list.slice(PER_DAY).map((a) => (
                          <li key={a.id}>
                            <Entry a={a} />
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <WeekGrid days={weekDays(weekFrom)} byDay={byDay} today={today} minutesOf={minutesOf} canPlan={canPlan} timeZone={timeZone} Entry={Entry} />
      )}
      {canPlan && <p className="mt-2 text-meta text-ink-3">Click an empty {mode === "month" ? "day" : "hour"} to plan a call there.</p>}
    </div>
  );
}

/** Side by side: each item's lane among those it overlaps on the same day. */
function lanes(items: { id: string; start: number; end: number }[]): Map<string, { lane: number; of: number }> {
  const out = new Map<string, { lane: number; of: number }>();
  const sorted = [...items].sort((a, b) => a.start - b.start || b.end - a.end);
  let group: typeof sorted = [];
  let groupEnd = -1;
  const close = () => {
    const ends: number[] = [];
    for (const it of group) {
      let lane = ends.findIndex((e) => e <= it.start);
      if (lane === -1) lane = ends.length;
      ends[lane] = it.end;
      out.set(it.id, { lane, of: 0 });
    }
    for (const it of group) out.get(it.id)!.of = ends.length;
    group = [];
  };
  for (const it of sorted) {
    if (it.start >= groupEnd && group.length) close();
    group.push(it);
    groupEnd = Math.max(groupEnd, it.end);
  }
  if (group.length) close();
  return out;
}

function WeekGrid({
  days,
  byDay,
  today,
  minutesOf,
  canPlan,
  timeZone,
  Entry,
}: {
  days: string[];
  byDay: Map<string, ActivityItem[]>;
  today: string;
  minutesOf: (a: ActivityItem) => number;
  canPlan: boolean;
  timeZone: string;
  Entry: (p: { a: ActivityItem; block?: boolean }) => React.ReactNode;
}) {
  const hours = Array.from({ length: TO_HOUR - FROM_HOUR }, (_, i) => FROM_HOUR + i);
  // The time now, moving, for the line across today.
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const tick = () => {
      const [h, m] = new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date()).split(":").map(Number);
      setNow(h * 60 + m);
    };
    tick();
    const t = window.setInterval(tick, 60_000);
    return () => window.clearInterval(t);
  }, [timeZone]);
  const label = new Intl.DateTimeFormat("en-PH", { weekday: "short", day: "numeric", timeZone: "UTC" });

  return (
    <div className="overflow-x-auto rounded-[10px] border border-rule">
      <div className="grid min-w-[52rem]" style={{ gridTemplateColumns: "3.5rem repeat(7, minmax(0, 1fr))" }}>
        <div className="border-b border-rule bg-[#fbfbfa]" />
        {days.map((d) => (
          <div key={d} className={`border-b border-l border-rule px-2 py-2 text-meta font-semibold ${d === today ? "bg-[#f1f7ee] text-ink" : "bg-[#fbfbfa] text-ink-2"}`}>
            {label.format(new Date(`${d}T00:00:00Z`))}
          </div>
        ))}
        {/* hour labels */}
        <div className="relative" style={{ height: hours.length * HOUR_PX }}>
          {hours.map((h, i) => (
            <span key={h} className="absolute right-2 -translate-y-1/2 text-[0.6875rem] text-ink-3 tabular-nums" style={{ top: i * HOUR_PX }}>
              {i === 0 ? "" : `${((h + 11) % 12) + 1} ${h < 12 ? "AM" : "PM"}`}
            </span>
          ))}
        </div>
        {days.map((d) => {
          const list = (byDay.get(d) ?? []).map((a) => {
            const start = Math.max(FROM_HOUR * 60, Math.min(minutesOf(a), TO_HOUR * 60 - 30));
            return { a, id: a.id, start, end: start + Math.max(30, a.durationMinutes ?? 45) };
          });
          const placed = lanes(list);
          return (
            <div key={d} className="relative border-l border-rule" style={{ height: hours.length * HOUR_PX }}>
              {hours.map((h, i) => (
                <div
                  key={h}
                  onClick={() => canPlan && planAt(d, h)}
                  title={canPlan ? `Plan a call at ${((h + 11) % 12) + 1} ${h < 12 ? "AM" : "PM"}` : undefined}
                  className={`absolute inset-x-0 border-t border-rule ${i === 0 ? "border-t-0" : ""} ${canPlan ? "cursor-pointer hover:bg-[#f7faf5]" : ""}`}
                  style={{ top: i * HOUR_PX, height: HOUR_PX }}
                />
              ))}
              {list.map(({ a, start, end }) => {
                const p = placed.get(a.id) ?? { lane: 0, of: 1 };
                const w = 100 / p.of;
                return (
                  <div
                    key={a.id}
                    className="absolute px-0.5"
                    style={{ top: ((start - FROM_HOUR * 60) / 60) * HOUR_PX + 1, height: Math.max(22, ((end - start) / 60) * HOUR_PX - 2), left: `${p.lane * w}%`, width: `${w}%` }}
                  >
                    <Entry a={a} block />
                  </div>
                );
              })}
              {d === today && now !== null && now >= FROM_HOUR * 60 && now <= TO_HOUR * 60 && (
                <div className="pointer-events-none absolute inset-x-0 z-10 border-t-2 border-danger" style={{ top: ((now - FROM_HOUR * 60) / 60) * HOUR_PX }} aria-hidden>
                  <span className="absolute -top-[5px] -left-[5px] size-2 rounded-full bg-danger" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
