/**
 * A ring of a few parts and their total, with a legend that names each part
 * and its count, so no part is told by its colour alone. Hovering a part shows
 * its figure. Parts with nothing are left out of the ring but kept in the legend.
 */
export type Slice = { label: string; value: number; color: string; note?: string };

const R = 44;
const RING = 2 * Math.PI * R;
const GAP = 2; // a gap of the card's own colour between parts

export function Donut({ title, slices, total, totalLabel = "Total" }: { title: string; slices: Slice[]; total?: number; totalLabel?: string }) {
  const sum = slices.reduce((s, x) => s + x.value, 0);
  const shown = slices.filter((s) => s.value > 0);
  let offset = 0;
  const arcs = shown.map((s) => {
    const length = (RING * s.value) / (sum || 1);
    const arc = { ...s, length: Math.max(0, length - (shown.length > 1 ? GAP : 0)), offset };
    offset += length;
    return arc;
  });
  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 120 120" className="size-28 shrink-0 -rotate-90" role="img" aria-label={`${title}: ${slices.map((s) => `${s.label} ${s.value}`).join(", ")}`}>
        <circle cx="60" cy="60" r={R} fill="none" stroke="var(--color-mint-2)" strokeWidth="14" />
        {arcs.map((a) => (
          <circle
            key={a.label}
            cx="60"
            cy="60"
            r={R}
            fill="none"
            stroke={a.color}
            strokeWidth="14"
            strokeDasharray={`${a.length} ${RING - a.length}`}
            strokeDashoffset={-a.offset}
          >
            <title>{`${a.label}: ${a.value}${a.note ? ` · ${a.note}` : ""}`}</title>
          </circle>
        ))}
        <g className="rotate-90" style={{ transformOrigin: "60px 60px" }}>
          {/* The number first, then what it counts. */}
          <text x="60" y="64" textAnchor="middle" className="fill-ink text-[1.5rem] font-semibold">
            {total ?? sum}
          </text>
          <text x="60" y="80" textAnchor="middle" className="fill-ink-3 text-[0.6875rem]">
            {totalLabel === "Total" ? (total ?? sum) === 1 ? "deal" : "deals" : totalLabel}
          </text>
        </g>
      </svg>
      {/* One column: each part's share first (what the eye reads), then its name and count. */}
      <ul className="min-w-0 flex-1 space-y-2 text-meta">
        {slices.map((s) => (
          <li key={s.label} className="flex items-baseline gap-2.5" title={s.note}>
            <span className="w-10 shrink-0 text-right text-sm font-semibold text-ink tabular-nums">{sum ? `${Math.round((100 * s.value) / sum)}%` : "—"}</span>
            <span className="size-2 shrink-0 translate-y-[-1px] rounded-full" style={{ background: s.color }} aria-hidden />
            <span className="min-w-0 flex-1 truncate text-ink-2">{s.label}</span>
            <span className="text-ink-3 tabular-nums">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// The palette, checked for colour-blind readers (the dataviz reference palette, light).
/** Parts that are just different (stages): always in this order. */
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
/** More to less (probability): one blue, darker for more. */
export const RAMP = ["#1c5cab", "#5598e7", "#9ec5f4"];
