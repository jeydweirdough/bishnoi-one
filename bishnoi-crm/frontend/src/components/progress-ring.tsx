/**
 * How far along something is, as a ring: the share filled in, the percentage
 * in the middle, and (optional) a tick where it should be by now. The status
 * colour only supports the words next to it; it never speaks alone.
 */
export type RingTone = "good" | "warn" | "bad" | "plain" | "none";

const STROKE: Record<RingTone, string> = {
  good: "var(--color-filed)",
  warn: "var(--color-due-today)",
  bad: "var(--color-danger)",
  plain: "var(--color-sage)",
  none: "var(--color-rule-strong)",
};

const R = 42;
const RING = 2 * Math.PI * R;

export function ProgressRing({
  pct,
  pace,
  tone = "plain",
  label,
  size = "md",
  center,
}: {
  /** How far along, as a percentage; above 100 shows full. Null: nothing to show yet. */
  pct: number | null;
  /** Where it should be by now, as a percentage of the whole. */
  pace?: number | null;
  tone?: RingTone;
  /** What it says, for screen readers: "Won 80% of the target". */
  label: string;
  /** xs: in a table cell. */
  size?: "xs" | "sm" | "md";
  /** What's in the middle; the percentage when not given. */
  center?: string;
}) {
  const filled = pct === null ? 0 : Math.max(0, Math.min(100, pct));
  const tick = pace !== null && pace !== undefined && pace > 0 && pace < 100 ? pace : null;
  const angle = tick !== null ? (tick / 100) * 2 * Math.PI - Math.PI / 2 : 0;
  return (
    <svg viewBox="0 0 100 100" className={`${size === "xs" ? "size-11" : size === "sm" ? "size-16" : "size-24"} shrink-0`} role="img" aria-label={label}>
      <circle cx="50" cy="50" r={R} fill="none" stroke="var(--color-mint-2)" strokeWidth={size === "xs" ? 12 : 9} />
      {filled > 0 && (
        <circle
          cx="50"
          cy="50"
          r={R}
          fill="none"
          stroke={STROKE[tone]}
          strokeWidth={size === "xs" ? 12 : 9}
          strokeLinecap="round"
          strokeDasharray={`${(RING * filled) / 100} ${RING}`}
          transform="rotate(-90 50 50)"
        />
      )}
      {tick !== null && (
        <line
          x1={50 + (R - 6) * Math.cos(angle)}
          y1={50 + (R - 6) * Math.sin(angle)}
          x2={50 + (R + 6) * Math.cos(angle)}
          y2={50 + (R + 6) * Math.sin(angle)}
          stroke="var(--color-ink)"
          strokeWidth="3"
          strokeLinecap="butt"
        >
          <title>Where it should be by today</title>
        </line>
      )}
      <text x="50" y="50" textAnchor="middle" dominantBaseline="central" className={`fill-ink font-semibold ${size === "xs" ? "text-[1.6rem]" : size === "sm" ? "text-[1.15rem]" : "text-[1.3rem]"}`}>
        {center ?? (pct === null ? "—" : `${Math.round(pct)}%`)}
      </text>
    </svg>
  );
}
