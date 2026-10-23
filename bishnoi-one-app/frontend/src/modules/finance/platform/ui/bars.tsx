import Link from "next/link";
import { Flag } from "@/src/modules/finance/platform/ui/marks";

/**
 * A few counts of the same thing, side by side, as bars.
 *
 * One hue, never several: these are one measure — items waiting, people, products —
 * and the row already says which is which, so a colour per bar would be decoration
 * standing in for a label. Length carries the comparison; the number is printed
 * beside it, so the bar never has to be measured by eye.
 *
 * Bars are drawn against the largest value present rather than a round number:
 * the question these answer is "which of these is the big one", not "how close to
 * a thousand".
 */
export type Bar = { label: string; value: number; href?: string; flag?: boolean };

export function Bars({ rows, unit }: { rows: Bar[]; unit?: string }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="mt-2 space-y-2.5">
      {rows.map((row) => {
        // A count above zero always shows as a sliver, so "some" never reads as "none".
        const share = row.value <= 0 ? 0 : Math.max(0.02, row.value / max);
        const flagged = Boolean(row.flag) && row.value > 0;
        const label = (
          <span className={`text-meta ${flagged ? "text-ink" : "text-ink-2"}`}>
            {flagged ? <Flag letter="!">{row.label}</Flag> : row.label}
          </span>
        );
        return (
          <li key={row.label}>
            <div className="flex items-baseline justify-between gap-3">
              {row.href ? (
                <Link href={row.href} className="min-w-0 truncate hover:underline">
                  {label}
                </Link>
              ) : (
                <span className="min-w-0 truncate">{label}</span>
              )}
              <span className="shrink-0 text-meta font-semibold text-ink [font-variant-numeric:proportional-nums]">
                {row.value}
                {unit ? <span className="font-normal text-ink-3"> {unit}</span> : null}
              </span>
            </div>
            {/* Hidden from screen readers on purpose: the number above it is the
                same fact in words, and a bar read aloud is noise. */}
            <div aria-hidden className="mt-1 h-1.5 overflow-hidden rounded-full bg-rule">
              <div
                className={`h-full rounded-full ${flagged ? "bg-eosin" : "bg-hema"}`}
                style={{ width: `${(share * 100).toFixed(1)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
