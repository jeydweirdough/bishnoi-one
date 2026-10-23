import { rateLabel } from "@/src/modules/finance/platform/lib/labels";
import { orgFormat } from "@/src/modules/finance/platform/lib/org";
import type { TrendPoint } from "@/src/modules/finance/platform/lib/types";

/** Twelve months at a glance, in the de-emphasis ink with the latest month marked. The numbers sit beside it. */
export async function Sparkline({ points }: { points: TrendPoint[] }) {
  const monthShort = (await orgFormat()).on({ month: "short", timeZone: "UTC" });
  const n = points.length;
  const at = (i: number, rate: number) => [(i / Math.max(1, n - 1)) * 92 + 4, (1 - rate) * 20 + 2] as const;
  let d = "";
  let pen = false;
  points.forEach((p, i) => {
    if (p.rate === null) return void (pen = false);
    const [px, py] = at(i, p.rate);
    d += `${pen ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)} `;
    pen = true;
  });
  const lastIndex = points.findLastIndex((p) => p.rate !== null);
  const summary = points.map((p) => `${monthShort.format(new Date(`${p.month}-01T00:00:00Z`))} ${rateLabel(p.rate)}`).join(", ");
  return (
    <svg viewBox="0 0 100 24" className="h-6 w-24" role="img" aria-label={`Retention by month: ${summary}`}>
      <path d={d} fill="none" stroke="var(--color-ink-3)" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      {lastIndex >= 0 && (
        <circle cx={at(lastIndex, points[lastIndex].rate!)[0]} cy={at(lastIndex, points[lastIndex].rate!)[1]} r="2.5" fill="var(--color-ink)" stroke="var(--color-sheet)" strokeWidth="1.5" />
      )}
    </svg>
  );
}
