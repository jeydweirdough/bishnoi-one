// The home page's two charts, drawn as plain SVG and HTML on the server: a
// card's trend line, and the overview's month bars.

/** Twelve months as a line in sage, the latest month marked. The numbers sit beside it. */
export function TrendLine({ values, label }: { values: number[]; label: string }) {
  const top = Math.max(1, ...values);
  const n = values.length;
  const at = (i: number, v: number) => [(i / Math.max(1, n - 1)) * 96 + 2, 26 - (v / top) * 22] as const;
  const d = values.map((v, i) => `${i ? "L" : "M"}${at(i, v)[0].toFixed(1)},${at(i, v)[1].toFixed(1)}`).join(" ");
  const [lx, ly] = at(n - 1, values[n - 1] ?? 0);
  return (
    <svg viewBox="0 0 100 30" className="h-9 w-20 shrink-0" role="img" aria-label={label}>
      <path d={`${d} L98,30 L2,30 Z`} fill="var(--color-sage)" opacity="0.18" />
      <path d={d} fill="none" stroke="var(--color-sage-deep)" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lx} cy={ly} r="2.4" fill="var(--color-sage-deep)" stroke="var(--color-sheet)" strokeWidth="1.2" />
    </svg>
  );
}

/**
 * The months as bars. Each shows its figure when pointed at; this month (or,
 * while it is empty, the latest with any) is solid, its figure always
 * showing. The others are hatched, so the eye goes to one.
 */
export function MonthBars({ points, unit }: { points: { label: string; long: string; value: number }[]; unit: string }) {
  const top = Math.max(1, ...points.map((p) => p.value));
  // This month; or, while it has nothing yet, the latest month that has.
  const latest = points.findLastIndex((p) => p.value > 0);
  const marked = points[points.length - 1]?.value || latest < 0 ? points.length - 1 : latest;
  return (
    <div role="img" aria-label={points.map((p) => `${p.long}: ${p.value} ${unit}`).join(", ")}>
      <div className="flex h-56 items-end gap-2 sm:gap-3" aria-hidden>
        {points.map((p, i) => {
          const on = i === marked;
          const h = Math.max(6, (p.value / top) * 100);
          return (
            <div key={p.long} className="group relative flex h-full flex-1 flex-col justify-end">
              <span
                className={`pointer-events-none absolute left-1/2 z-10 -translate-x-1/2 rounded-md bg-ink px-3 py-1.5 text-center whitespace-nowrap text-white shadow-overlay transition-opacity ${
                  on ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                }`}
                style={{ bottom: `calc(${h}% + 12px)` }}
              >
                <span className="block text-[0.6875rem] text-white/70">{p.long}</span>
                <span className="block text-sm font-semibold tabular-nums">
                  {p.value.toLocaleString()} {unit}
                </span>
              </span>
              <span
                className={`block w-full rounded-md border transition-colors ${
                  on ? "border-ink bg-ink" : "border-rule-strong bg-sheet group-hover:border-ink-3"
                }`}
                style={{
                  height: `${h}%`,
                  backgroundImage: on ? undefined : "repeating-linear-gradient(135deg, var(--color-rule) 0 2px, transparent 2px 7px)",
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-2 sm:gap-3" aria-hidden>
        {points.map((p, i) => (
          <span key={p.long} className={`flex-1 text-center text-meta ${i === marked ? "font-semibold text-ink" : "text-ink-3"}`}>
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}
