import { ToggleLinks } from "../ui/toggle-links";
import { Sheet } from "../ui/sheet";

// The profile's two activity charts: what the person did each day (in the CRM,
// activities and visits; elsewhere, their entries in the activity log), on the
// company's own days.

/** Day keys ("2026-10-14") moved by whole days. */
export function addDays(key: string, n: number): string {
  const d = new Date(`${key}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** Monday of the week a day is in. */
export function mondayOf(key: string): string {
  const day = new Date(`${key}T00:00:00Z`).getUTCDay();
  return addDays(key, -((day + 6) % 7));
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
/** How many weeks the grid shows: about three months. */
export const HEAT_WEEKS = 13;

const done = (n: number) => `${n} done`;

/** One week, a bar a day: today's (or the week's) count large, the busiest day the bar's full height. */
export function WeekBars({ days, today, week, base }: { days: Record<string, number>; today: string; week: 0 | 1; base: string }) {
  const start = addDays(mondayOf(today), -7 * week);
  const keys = DAYS.map((_, i) => addDays(start, i));
  const counts = keys.map((k) => days[k] ?? 0);
  const most = Math.max(1, ...counts);
  const total = counts.reduce((a, b) => a + b, 0);
  return (
    <Sheet className="px-5 pt-4 pb-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-heading text-ink">Activity</h2>
        <ToggleLinks
          current={String(week)}
          options={[
            { value: "0", label: "This week", href: base },
            { value: "1", label: "Last week", href: `${base}${base.includes("?") ? "&" : "?"}week=1` },
          ]}
        />
      </div>
      <p className="mt-3 text-meta text-ink-3">{week === 0 ? "Today" : "That week"}</p>
      <p className="text-[1.75rem] leading-tight font-semibold text-ink tabular-nums">{done(week === 0 ? (days[today] ?? 0) : total)}</p>
      {week === 0 && <p className="text-meta text-ink-3">{done(total)} this week</p>}
      <ol className="mt-4 grid h-36 grid-cols-7 items-end gap-2" aria-label="Completed each day">
        {keys.map((k, i) => {
          const n = counts[i];
          const now = k === today;
          const later = k > today;
          return (
            <li key={k} className="flex h-full flex-col items-center justify-end gap-1.5" title={later ? `${DAYS[i]}: still to come` : `${DAYS[i]}: ${done(n)}`}>
              <span className="relative flex w-full flex-1 items-end overflow-hidden rounded-md bg-hema-tint/70">
                <span
                  className={`block w-full rounded-md transition-[height] duration-500 ${now ? "bg-sage-deep" : "bg-sage"}`}
                  style={{ height: later ? 0 : `${Math.max(n ? 8 : 0, (100 * n) / most)}%` }}
                />
              </span>
              <span className={`text-meta ${now ? "font-semibold text-ink" : "text-ink-3"}`}>{DAYS[i][0]}</span>
              <span className="sr-only">{later ? "still to come" : done(n)}</span>
            </li>
          );
        })}
      </ol>
    </Sheet>
  );
}

const SHADES = ["bg-hema-tint", "bg-sage/45", "bg-sage", "bg-[#7fae6f]", "bg-sage-deep"];

/** About three months, a square a day (a column a week, Monday at the top): the darker, the more got done. */
export function Heatmap({ days, today }: { days: Record<string, number>; today: string }) {
  const start = addDays(mondayOf(today), -7 * (HEAT_WEEKS - 1));
  const weeks = Array.from({ length: HEAT_WEEKS }, (_, w) => Array.from({ length: 7 }, (_, d) => addDays(start, 7 * w + d)));
  const most = Math.max(1, ...Object.values(days));
  const shade = (n: number) => SHADES[n ? Math.max(1, Math.ceil((4 * n) / most)) : 0];
  const total = weeks.flat().reduce((sum, k) => sum + (k <= today ? (days[k] ?? 0) : 0), 0);
  const active = weeks.flat().filter((k) => k <= today && days[k]).length;
  return (
    <Sheet className="px-5 pt-4 pb-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-heading text-ink">Activity</h2>
        <span className="text-meta text-ink-3">Last 3 months</span>
      </div>
      <p className="mt-1 mb-4 text-meta text-ink-3">
        {done(total)} on {active} {active === 1 ? "day" : "days"}
      </p>
      <div className="flex gap-2" role="img" aria-label={`Completed each day over the last 3 months: ${done(total)} on ${active} days`}>
        <div className="grid grid-rows-7 gap-1 text-[0.625rem] leading-none text-ink-3" aria-hidden>
          {DAYS.map((d) => (
            <span key={d} className="flex h-full items-center">
              {d[0]}
            </span>
          ))}
        </div>
        <div className="grid flex-1 grid-flow-col grid-rows-7 gap-1" aria-hidden>
          {weeks.flat().map((k) =>
            k > today ? (
              <span key={k} className="aspect-square rounded-[3px]" />
            ) : (
              <span key={k} title={`${k}: ${done(days[k] ?? 0)}`} className={`aspect-square rounded-[3px] ${shade(days[k] ?? 0)} ${k === today ? "ring-1 ring-ink/40" : ""}`} />
            ),
          )}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-end gap-1 text-[0.625rem] text-ink-3" aria-hidden>
        Less
        {SHADES.map((s) => (
          <span key={s} className={`size-2.5 rounded-[2px] ${s}`} />
        ))}
        More
      </div>
    </Sheet>
  );
}
