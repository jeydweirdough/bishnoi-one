"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { logStep } from "@/src/actions/operations";
import type { CountdownHighlight } from "@/src/platform/lib/types";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Icon, type IconName } from "@/src/platform/ui/icons";

// Home's work laid out in time, so it comes a day at a time instead of all at
// once: a week strip with how much falls due each day, "Late" as its own day,
// and the chosen day's lines under it, each with its one step.

const ICON: Record<string, IconName> = {
  permit: "permits",
  immigration: "immigration",
  document: "documents",
  property: "properties",
  ticket: "tickets",
  vehicle_registration: "vehicles",
  vehicle_insurance: "vehicles",
  vehicle_pms: "vehicles",
  travel: "travel",
  material: "approvals",
};
// What each icon stands for, shown when it's hovered.
const KIND: Record<string, string> = {
  permit: "Permit",
  immigration: "Expatriate document",
  document: "Corporate document",
  property: "Lease",
  ticket: "Office request",
  vehicle_registration: "Vehicle registration",
  vehicle_insurance: "Vehicle insurance",
  vehicle_pms: "Vehicle maintenance (PMS)",
  travel: "Hotel or flight",
  material: "Promotional material",
};
const STEP: Record<string, { action: string; label: string }> = {
  vehicle_registration: { action: "registration_renewed", label: "Renewed" },
  vehicle_insurance: { action: "insurance_renewed", label: "Renewed" },
  vehicle_pms: { action: "pms_done", label: "PMS done" },
};
const SHOWN = 5;
const LATE = "late";

const keyOf = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dateOf = (key: string) => new Date(`${key}T00:00:00`);
const titleOf = (i: CountdownHighlight) => `${i.title}${i.entityType.startsWith("vehicle_") ? `: ${i.subtitle.charAt(0).toLowerCase() + i.subtitle.slice(1)}` : ""}`;
const subOf = (i: CountdownHighlight) => (i.entityType.startsWith("vehicle_") ? i.reference : i.subtitle);

function dayName(key: string, today: string): string {
  if (key === LATE) return "Late";
  const label = dateOf(key).toLocaleDateString("en-PH", { weekday: "long", day: "numeric", month: "long" });
  if (key === today) return `Today, ${label}`;
  const tomorrow = new Date(dateOf(today));
  tomorrow.setDate(tomorrow.getDate() + 1);
  return key === keyOf(tomorrow) ? `Tomorrow, ${label}` : label;
}

/** Today's date and time, kept current, for the page's line under its title. */
export function Clock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);
  if (!now) return null;
  return (
    <>
      {now.toLocaleDateString("en-PH", { weekday: "long", day: "numeric", month: "long", year: "numeric" })} ·{" "}
      {now.toLocaleTimeString("en-PH", { hour: "numeric", minute: "2-digit" })}
    </>
  );
}

/**
 * What falls due, a day at a time, as a calendar app's schedule: a week strip
 * (with Late as its own day first), and the chosen day's lines under it, each
 * with its one step. One card, one list on screen.
 */
export function HomeCalendar({ items, canLog }: { items: CountdownHighlight[]; canLog: boolean }) {
  const router = useRouter();
  const today = keyOf(new Date());
  const [done, setDone] = useState<string[]>([]);
  const [pending, start] = useTransition();
  const open = items.filter((i) => !done.includes(`${i.entityType}-${i.entityId}`));

  // Each line on its day; anything before today is Late.
  const byDay = useMemo(() => {
    const out = new Map<string, CountdownHighlight[]>();
    for (const i of open) {
      const day = i.daysRemaining < 0 ? LATE : i.dueDate.slice(0, 10);
      out.set(day, [...(out.get(day) ?? []), i]);
    }
    for (const list of out.values()) list.sort((a, b) => a.daysRemaining - b.daysRemaining);
    return out;
  }, [open]);
  const late = byDay.get(LATE)?.length ?? 0;
  const days = [...byDay.keys()].filter((k) => k !== LATE).sort();

  // Opens on what needs you first: Late, else today, else the next day with something.
  const [chosen, setChosen] = useState<string>(() => (late ? LATE : byDay.has(today) ? today : (days[0] ?? today)));
  const mondayOf = (key: string) => {
    const d = dateOf(key);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return keyOf(d);
  };
  const [week, setWeek] = useState(() => mondayOf(chosen === LATE ? today : chosen));
  const strip = Array.from({ length: 7 }, (_, n) => {
    const d = dateOf(week);
    d.setDate(d.getDate() + n);
    return keyOf(d);
  });
  const thisWeek = mondayOf(today);
  const lastWeek = days.length ? mondayOf(days[days.length - 1]) : thisWeek;
  const shift = (weeks: number) => {
    const d = dateOf(week);
    d.setDate(d.getDate() + weeks * 7);
    setWeek(keyOf(d));
  };
  const weekCount = strip.reduce((n, k) => n + (byDay.get(k)?.length ?? 0), 0);

  const lines = byDay.get(chosen) ?? [];
  const nextDay = days.find((k) => k > (chosen === LATE ? today : chosen) && k >= today);

  function choose(day: string) {
    setChosen(day);
    if (day !== LATE) setWeek(mondayOf(day));
  }

  const month = dateOf(strip[0]).toLocaleDateString("en-PH", { month: "long", year: "numeric" });
  const monthEnd = dateOf(strip[6]).toLocaleDateString("en-PH", { month: "long", year: "numeric" });

  return (
    <section className="flex flex-col rounded-[22px] border border-rule bg-sheet">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5">
        <div>
          <h2 className="text-[17px] font-semibold text-ink">Schedule</h2>
          <p className="text-[12.5px] text-ink-3">
            {month === monthEnd ? month : `${month.split(" ")[0]} – ${monthEnd}`} · {weekCount} due this week
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" aria-label="Previous week" disabled={week <= thisWeek} onClick={() => shift(-1)} className="grid size-8 place-items-center rounded-full text-ink-2 hover:bg-mint disabled:opacity-30">
            <ChevronLeft className="size-4" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => choose(today)}
            className={`h-8 rounded-full border px-3 text-[13px] font-medium ${chosen === today ? "border-ink bg-ink text-white" : "border-rule-strong text-ink hover:border-ink"}`}
          >
            Today
          </button>
          <button type="button" aria-label="Next week" disabled={week >= lastWeek} onClick={() => shift(1)} className="grid size-8 place-items-center rounded-full text-ink-2 hover:bg-mint disabled:opacity-30">
            <ChevronRight className="size-4" aria-hidden />
          </button>
        </div>
      </div>

      <div className="mt-3 flex gap-1.5 overflow-x-auto px-5 pt-2.5 pb-1" role="tablist" aria-label="Days">
        {late > 0 && (
          <DayPill selected={chosen === LATE} onClick={() => choose(LATE)} top="Past due" big="Late" count={late} tone="late" label={`Late, ${late} past their date`} />
        )}
        {late > 0 && <span className="mx-1 w-px shrink-0 self-stretch bg-rule" aria-hidden />}
        {strip.map((key) => {
          const d = dateOf(key);
          const count = byDay.get(key)?.length ?? 0;
          const past = key < today;
          return (
            <DayPill
              key={key}
              selected={chosen === key}
              today={key === today}
              disabled={past}
              onClick={() => choose(key)}
              top={d.toLocaleDateString("en-PH", { weekday: "short" })}
              big={String(d.getDate())}
              count={count}
              tone={!past && (d.getTime() - dateOf(today).getTime()) / 864e5 <= 7 ? "soon" : "plain"}
              label={`${dayName(key, today)}${count ? `, ${count} due` : ""}`}
            />
          );
        })}
      </div>

      <div className="mt-3 flex-1 border-t border-rule px-5 pt-4 pb-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-[15px] font-semibold text-ink">{chosen === LATE ? "Late: past their date" : dayName(chosen, today)}</h3>
          {lines.length > 0 && <span className="text-[12.5px] text-ink-3">{lines.length} {lines.length === 1 ? "item" : "items"}</span>}
        </div>

        {lines.length === 0 ? (
          <div className="mt-2 text-sm text-ink-2">
            Nothing falls due on this day.{" "}
            {nextDay ? (
              <button type="button" onClick={() => choose(nextDay)} className="font-semibold text-ink underline">
                Next: {dayName(nextDay, today)} ({byDay.get(nextDay)!.length})
              </button>
            ) : (
              <span className="text-ink-3">Nothing else in the next 60 days.</span>
            )}
          </div>
        ) : (
          <ul className="mt-1">
            {lines.slice(0, SHOWN).map((i) => {
              const step = canLog ? STEP[i.entityType] : undefined;
              const key = `${i.entityType}-${i.entityId}`;
              return (
                <li key={key} className="flex items-center gap-3.5 border-b border-rule/70 py-3 last:border-0">
                  {/* What it is, before its name: the icon, and its name on hover or focus. */}
                  <span tabIndex={0} aria-label={KIND[i.entityType] ?? "Alert"} className="group relative grid size-9 shrink-0 place-items-center rounded-full bg-mint text-ink outline-none hover:bg-mint-2 focus-visible:ring-2 focus-visible:ring-ink">
                    <Icon name={ICON[i.entityType] ?? "notifications"} className="size-4" />
                    <span role="tooltip" className="pointer-events-none absolute top-full left-0 z-20 mt-1.5 hidden rounded-[8px] bg-ink px-2 py-1 text-[11.5px] font-medium whitespace-nowrap text-white shadow-overlay group-hover:block group-focus-visible:block">
                      {KIND[i.entityType] ?? "Alert"}
                    </span>
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link href={i.actionPath} className="block truncate text-[14px] font-semibold text-ink hover:underline">
                      {titleOf(i)}
                    </Link>
                    <p className="truncate text-[12.5px] text-ink-3">
                      {i.daysRemaining < 0 && <span className="font-medium text-danger">{Math.abs(i.daysRemaining)} days late · </span>}
                      {subOf(i)}
                    </p>
                  </div>
                  {step ? (
                    <Button
                      size="sm"
                      disabled={pending}
                      onClick={() =>
                        start(async () => {
                          const r = await logStep("vehicles", i.entityId, step.action);
                          if (!r.ok) return void toast.error(r.error);
                          setDone((d) => [...d, key]);
                          toast.success(step.label === "PMS done" ? "PMS done" : `${i.subtitle} renewed`, { description: i.title });
                          router.refresh();
                        })
                      }
                    >
                      {step.label}
                    </Button>
                  ) : (
                    <LinkButton href={i.actionPath} size="sm" variant="quiet">
                      Open
                    </LinkButton>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {lines.length > SHOWN && (
          <p className="mt-3 text-[13px] text-ink-2">
            {lines.length - SHOWN} more {chosen === LATE ? "late" : "on this day"}.{" "}
            <Link href="/notifications" className="font-semibold text-ink underline">
              See all in Renewal alerts
            </Link>
          </p>
        )}
      </div>
    </section>
  );
}

/** One day in the week strip: its weekday, date and how much falls due. */
function DayPill({
  selected,
  today,
  disabled,
  onClick,
  top,
  big,
  count,
  tone,
  label,
}: {
  selected: boolean;
  today?: boolean;
  disabled?: boolean;
  onClick: () => void;
  top: string;
  big: string;
  count: number;
  tone: "late" | "soon" | "plain";
  label: string;
}) {
  const look = selected
    ? tone === "late"
      ? "bg-danger text-white"
      : "bg-ink text-white"
    : tone === "late"
      ? "bg-danger-tint text-danger hover:brightness-95"
      : today
        ? "border-[1.5px] border-ink text-ink hover:bg-mint"
        : disabled
          ? "text-ink-3/60"
          : "text-ink hover:bg-mint";
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={`relative flex w-[58px] shrink-0 flex-col items-center rounded-[16px] py-2.5 sm:w-auto sm:flex-1 ${look}`}
    >
      <span className={`text-[11.5px] font-medium ${selected ? "text-white/80" : tone === "late" ? "" : "text-ink-3"}`}>{top}</span>
      <span className="text-[18px] leading-tight font-semibold">{big}</span>
      {/* How much falls due, in the top-right corner like a notification badge; Late's carries the "!". */}
      {count > 0 && (
        <span
          aria-hidden
          className={`absolute -top-2 -right-1 inline-flex h-[20px] min-w-[20px] items-center justify-center gap-0.5 rounded-full px-1.5 text-[11px] leading-none font-semibold ring-2 ring-sheet ${
            tone === "late" ? "bg-danger text-white" : selected ? "bg-ink text-white" : tone === "soon" ? "bg-[#e0a43a] text-white" : "bg-ink-2 text-white"
          }`}
        >
          {tone === "late" && <span className="font-bold">!</span>}
          {count}
        </span>
      )}
    </button>
  );
}
