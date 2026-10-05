import type { Traffic } from "@/src/lib/types";

// The Platform API's requests over a stretch of time, a bar per few minutes.
// Each bar sits where its minutes fall, so a quiet stretch shows as a gap
// rather than being squeezed out. The failed part of a bar is hatched and
// red, and named in the legend, so it doesn't rest on colour; the same
// figures are in a table underneath for anyone who can't see the bars.

const ZONE = "Asia/Manila";

/** A round number at or above n, for the top of the scale: 1, 2, 5, 10, 20, 50… */
function ceiling(n: number): number {
  if (n <= 1) return 1;
  const power = 10 ** Math.floor(Math.log10(n));
  for (const step of [1, 2, 5, 10]) if (step * power >= n) return step * power;
  return 10 * power;
}

export function TrafficChart({ traffic, now }: { traffic: Traffic; now: number }) {
  const range = traffic.hours * 3600_000;
  const start = now - range;
  const barWidth = (traffic.minutesPerBar * 60_000) / range;
  const bars = traffic.series.map((b) => ({ ...b, x: (Date.parse(b.at) - start) / range })).filter((b) => b.x + barWidth > 0 && b.x < 1);
  const top = ceiling(Math.max(0, ...bars.map((b) => b.requests)));
  const long = traffic.hours > 24;
  const tick = new Intl.DateTimeFormat("en-PH", long ? { timeZone: ZONE, weekday: "short", day: "numeric" } : { timeZone: ZONE, hour: "numeric", minute: "2-digit" });
  const full = new Intl.DateTimeFormat("en-PH", { timeZone: ZONE, dateStyle: "medium", timeStyle: "short" });
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({ f, label: f === 1 ? "Now" : tick.format(new Date(start + f * range)) }));
  const per = traffic.minutesPerBar === 1 ? "minute" : `${traffic.minutesPerBar} minutes`;
  const busiest = bars.reduce<(typeof bars)[number] | null>((m, b) => (!m || b.requests > m.requests ? b : m), null);
  const failed = bars.reduce((n, b) => n + b.failed, 0);
  const summary =
    bars.length === 0
      ? `No requests to the Platform API in the last ${traffic.hours} hours.`
      : `Requests to the Platform API per ${per} over the last ${traffic.hours} hours: ${traffic.summary.requests.toLocaleString("en-PH")} in all, ${failed.toLocaleString("en-PH")} failed.${
          busiest ? ` Busiest: ${busiest.requests.toLocaleString("en-PH")} at ${full.format(new Date(busiest.at))}.` : ""
        }`;

  return (
    <figure>
      <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
        {/* The scale: requests per bar. */}
        <div aria-hidden className="flex h-44 flex-col justify-between text-right text-tick text-ink-3 tabular-nums">
          <span className="-translate-y-1/2">{top.toLocaleString("en-PH")}</span>
          <span>{(top / 2).toLocaleString("en-PH")}</span>
          <span className="translate-y-1/2">0</span>
        </div>
        <svg viewBox="0 0 1000 200" preserveAspectRatio="none" className="h-44 w-full overflow-visible" role="img" aria-label={summary}>
          <defs>
            <pattern id="failed-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="var(--color-danger)" />
              <rect width="2" height="6" fill="var(--color-sheet)" opacity="0.55" />
            </pattern>
          </defs>
          {[0, 0.5, 1].map((f) => (
            <line key={f} x1="0" x2="1000" y1={200 - f * 200} y2={200 - f * 200} stroke="var(--color-rule)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          {bars.map((b) => {
            const x = Math.max(0, b.x) * 1000;
            const w = Math.max(1, barWidth * 1000 - 1.5);
            const h = (b.requests / top) * 200;
            const hf = (b.failed / top) * 200;
            return (
              <g key={b.at}>
                <title>{`${full.format(new Date(b.at))}: ${b.requests} requests, ${b.failed} failed, ${b.refused} refused${b.averageMs != null ? `, ${b.averageMs} ms on average` : ""}`}</title>
                <rect x={x} y={200 - h} width={w} height={h} fill="var(--color-hema)" />
                {b.failed > 0 && <rect x={x} y={200 - h} width={w} height={Math.max(hf, 2)} fill="url(#failed-hatch)" />}
              </g>
            );
          })}
        </svg>
        <span />
        <div aria-hidden className="relative mt-1.5 h-4 text-tick text-ink-3">
          {ticks.map((t) => (
            <span
              key={t.f}
              className="absolute whitespace-nowrap"
              style={t.f === 0 ? { left: 0 } : t.f === 1 ? { right: 0 } : { left: `${t.f * 100}%`, transform: "translateX(-50%)" }}
            >
              {t.label}
            </span>
          ))}
        </div>
      </div>
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-meta text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-3 rounded-[1px] bg-hema" /> Requests, a bar per {per}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <svg aria-hidden className="size-3" viewBox="0 0 12 12">
            <rect width="12" height="12" fill="url(#failed-hatch)" />
          </svg>
          Failed (the API&apos;s own errors)
        </span>
      </figcaption>
      {bars.length > 0 && (
        <details className="mt-3 text-meta">
          <summary className="cursor-pointer text-hema">Show the figures as a table</summary>
          <div className="mt-2 max-h-72 overflow-auto">
            <table className="w-full text-left tabular-nums">
              <thead className="sticky top-0 bg-sheet text-ink-3">
                <tr>
                  <th className="py-1 pr-4 font-medium">From</th>
                  <th className="py-1 pr-4 text-right font-medium">Requests</th>
                  <th className="py-1 pr-4 text-right font-medium">Failed</th>
                  <th className="py-1 pr-4 text-right font-medium">Refused</th>
                  <th className="py-1 text-right font-medium">Average</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {[...bars].reverse().map((b) => (
                  <tr key={b.at}>
                    <td className="py-1 pr-4">{full.format(new Date(b.at))}</td>
                    <td className="py-1 pr-4 text-right">{b.requests}</td>
                    <td className="py-1 pr-4 text-right">{b.failed}</td>
                    <td className="py-1 pr-4 text-right">{b.refused}</td>
                    <td className="py-1 text-right">{b.averageMs != null ? `${b.averageMs} ms` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </figure>
  );
}
