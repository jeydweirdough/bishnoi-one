import type { Format } from "@/src/platform/lib/format";
import { Sheet } from "@/src/platform/ui/sheet";
import type { FieldCounts } from "@/src/modules/crm/components/field/types";
import { MEASURES, progress } from "@/src/modules/crm/components/field/words";
import { worded, type Terms } from "@/src/modules/crm/components/terms/terms";

/** One goal: what's done, what the goal is, and a bar for how far along. */
export function Meter({ label, actual, goal, money, fmt }: { label: string; actual: number; goal: number | null | undefined; money?: boolean; fmt: Format }) {
  const show = (n: number) => (money ? fmt.peso(n) : String(n));
  const pct = progress(actual, goal);
  return (
    <div className="min-w-0 px-5 py-4">
      <span className="block text-figure text-ink">{show(actual)}</span>
      <span className="mt-0.5 block text-meta text-ink-3">
        {label}
        {goal ? <> · goal {show(goal)}</> : " · no goal set"}
      </span>
      {pct !== null && (
        <>
          {/* The words above say the same; the bar is only for the eye. */}
          <div aria-hidden className="mt-2 h-1.5 overflow-hidden rounded-full bg-rule">
            <div className={`h-full rounded-full ${pct >= 100 ? "bg-hema" : "bg-hema/60"}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="mt-1 block text-meta text-ink-2">{pct >= 100 ? "Goal reached" : `${pct}% of the goal`}</span>
        </>
      )}
    </div>
  );
}

/** The four goals side by side. */
export function Meters({ actual, goal, fmt, terms }: { actual: FieldCounts; goal: FieldCounts | null; fmt: Format; terms: Terms }) {
  return (
    <Sheet className="mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule xl:grid-cols-4 [&>*]:bg-sheet">
      {MEASURES.map((m) => (
        <Meter key={m.key} label={worded(m.label, terms)} actual={actual[m.key]} goal={goal?.[m.key]} money={m.money} fmt={fmt} />
      ))}
    </Sheet>
  );
}
