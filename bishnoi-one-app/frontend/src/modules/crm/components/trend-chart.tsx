"use client";

import { useId, useState } from "react";
import { makeFormat } from "@/src/platform/lib/format";
import { rateLabel } from "@/src/platform/lib/labels";
import type { Org, TrendPoint } from "@/src/platform/lib/types";
const TICKS = [0, 0.25, 0.5, 0.75, 1];

const x = (i: number, n: number) => (n > 1 ? (i / (n - 1)) * 100 : 50);
const y = (rate: number) => (1 - rate) * 100;

/** The line, broken wherever a month had nobody to measure. */
function segments(points: TrendPoint[]): [number, number][][] {
  const runs: [number, number][][] = [];
  let run: [number, number][] = [];
  points.forEach((p, i) => {
    if (p.rate === null) {
      if (run.length) runs.push(run);
      run = [];
    } else run.push([x(i, points.length), y(p.rate)]);
  });
  if (run.length) runs.push(run);
  return runs;
}

function detail(p: TrendPoint) {
  return p.rate === null ? "Nobody to measure" : `${p.retained} of ${p.base} customers kept`;
}

/**
 * Retention by month: one series, so no legend (the heading names it). The
 * plot stretches to its box while text and dots stay HTML at real size, so it
 * reads the same on a phone. Hover or arrow keys show a month; the table below
 * has every number without either.
 */
export function TrendChart({ points, title, org }: { points: TrendPoint[]; title: string; org: Org }) {
  const fmt = makeFormat(org);
  const monthShort = fmt.on({ month: "short", timeZone: "UTC" });
  const monthLong = fmt.on({ month: "long", year: "numeric", timeZone: "UTC" });
  const asOfDay = fmt.on({ month: "short", day: "numeric", timeZone: "UTC" });
  const [active, setActive] = useState<number | null>(null);
  const tableId = useId();
  const n = points.length;
  const runs = segments(points);
  const lastIndex = points.findLastIndex((p) => p.rate !== null);
  const last = lastIndex >= 0 ? points[lastIndex] : null;
  const shown = active !== null ? points[active] : null;

  function pick(clientX: number, box: DOMRect) {
    const i = Math.round(((clientX - box.left) / box.width) * (n - 1));
    setActive(Math.max(0, Math.min(n - 1, i)));
  }

  return (
    <figure>
      <figcaption className="sr-only">{title}</figcaption>
      <div className="relative mt-2 mr-12 mb-7 ml-10 h-44">
        <svg className="absolute inset-0 size-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {TICKS.map((t) => (
            <line key={t} x1="0" x2="100" y1={y(t)} y2={y(t)} stroke="var(--color-rule)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          {runs.map((run, i) => (
            <g key={i}>
              {run.length > 1 && (
                <path
                  d={`M${run[0][0]},100 ${run.map(([px, py]) => `L${px},${py}`).join(" ")} L${run[run.length - 1][0]},100 Z`}
                  fill="var(--color-ink)"
                  fillOpacity="0.07"
                />
              )}
              <path
                d={run.map(([px, py], j) => `${j ? "L" : "M"}${px},${py}`).join(" ")}
                fill="none"
                stroke="var(--color-ink)"
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
            </g>
          ))}
          {active !== null && (
            <line x1={x(active, n)} x2={x(active, n)} y1="0" y2="100" stroke="var(--color-control)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          )}
        </svg>

        {/* Axis text, recessive. */}
        {TICKS.map((t) => (
          <span key={t} className="absolute -left-10 w-8 -translate-y-1/2 text-right text-tick text-ink-3 tabular-nums" style={{ top: `${y(t)}%` }} aria-hidden>
            {t * 100}%
          </span>
        ))}
        {points.map((p, i) => (
          <span
            key={p.month}
            className={`absolute -bottom-6 -translate-x-1/2 text-tick text-ink-3 ${(n - 1 - i) % 3 ? "max-sm:hidden" : ""}`}
            style={{ left: `${x(i, n)}%` }}
            aria-hidden
          >
            {monthShort.format(new Date(`${p.month}-01T00:00:00Z`))}
          </span>
        ))}

        {/* The latest value, labelled at the end of the line. */}
        {last && last.rate !== null && (
          <>
            <span
              className="absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink ring-2 ring-sheet"
              style={{ left: `${x(lastIndex, n)}%`, top: `${y(last.rate)}%` }}
              aria-hidden
            />
            <span className="absolute left-[calc(100%+0.5rem)] -translate-y-1/2 text-meta font-semibold" style={{ top: `${y(last.rate)}%` }} aria-hidden>
              {rateLabel(last.rate)}
            </span>
          </>
        )}

        {shown && shown.rate !== null && active !== lastIndex && (
          <span
            className="absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink ring-2 ring-sheet"
            style={{ left: `${x(active!, n)}%`, top: `${y(shown.rate)}%` }}
            aria-hidden
          />
        )}

        {/* Hit area: the whole plot. The crosshair finds the month; nobody has to land on a 2px line. */}
        <div
          tabIndex={0}
          role="group"
          aria-roledescription="chart"
          aria-label={`${title}. Use the left and right arrow keys to read each month.`}
          aria-describedby={tableId}
          className="absolute inset-0 cursor-crosshair rounded-full focus-visible:outline-2 focus-visible:outline-offset-4"
          onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive(active ?? n - 1)}
          onBlur={() => setActive(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") setActive(Math.max(0, (active ?? n - 1) - 1));
            else if (e.key === "ArrowRight") setActive(Math.min(n - 1, (active ?? n - 1) + 1));
            else return;
            e.preventDefault();
          }}
        />

        {shown && (
          <div
            role="status"
            className="pointer-events-none absolute top-0 z-10 w-max max-w-48 rounded-md bg-sheet px-2.5 py-1.5 text-meta shadow-overlay"
            style={{
              left: `${x(active!, n)}%`,
              transform: `translateX(${x(active!, n) > 60 ? "calc(-100% - 10px)" : "10px"})`,
            }}
          >
            <p className="flex items-center gap-1.5 font-semibold text-ink">
              <span aria-hidden className="inline-block h-0.5 w-3 rounded-full bg-ink" />
              {rateLabel(shown.rate)}
            </p>
            <p className="text-ink-2">{detail(shown)}</p>
            <p className="text-ink-3">
              {monthLong.format(new Date(`${shown.month}-01T00:00:00Z`))}
              {active === n - 1 && ` (to ${asOfDay.format(new Date(`${shown.asOf}T00:00:00Z`))})`}
            </p>
          </div>
        )}
      </div>

      <details className="mt-1 text-meta">
        <summary className="cursor-pointer text-ink-2">Show the numbers</summary>
        <table id={tableId} className="mt-2 w-full max-w-md text-left">
          <thead>
            <tr className="border-b border-rule text-caps text-ink-3 uppercase">
              <th scope="col" className="py-1.5 pr-3 font-semibold">Month</th>
              <th scope="col" className="py-1.5 pr-3 text-right font-semibold">Retention</th>
              <th scope="col" className="py-1.5 text-right font-semibold">Kept</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule tabular-nums">
            {points.map((p) => (
              <tr key={p.month}>
                <td className="py-1.5 pr-3">{monthLong.format(new Date(`${p.month}-01T00:00:00Z`))}</td>
                <td className="py-1.5 pr-3 text-right font-semibold">{rateLabel(p.rate)}</td>
                <td className="py-1.5 text-right text-ink-2">{p.base ? `${p.retained} of ${p.base}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
