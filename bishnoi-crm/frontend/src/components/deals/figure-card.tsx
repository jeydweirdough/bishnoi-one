import type { ReactNode } from "react";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { Bone, Chart } from "@/src/platform/ui/skeleton";

// The figure cards and breakdowns of the Deals page, shared with the dashboard
// so both read the same way: the figure first, large; what it is under it;
// then how it compares.

export { FigureCard, FigureCardLoading, type Figure } from "@/src/platform/ui/figures";

/** A breakdown while its figures are on the way: its title now, the share and chart when they land. */
export function BreakdownLoading({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <Sheet className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-caps text-ink-3 uppercase">{title}</p>
        {action}
      </div>
      <Bone className="mt-3 h-6 w-40" />
      <div className="mt-4">
        <Chart bars={8} />
      </div>
    </Sheet>
  );
}

/** A breakdown: its headline share first, then the chart that shows the rest; a drawing while it's empty. */
export function Breakdown({
  value,
  label,
  title,
  empty,
  emptyNote = "It fills in as deals are added.",
  art,
  action,
  children,
}: {
  value: string;
  label: string;
  title: string;
  empty?: string;
  emptyNote?: ReactNode;
  art?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Sheet className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-caps text-ink-3 uppercase">{title}</p>
        {action}
      </div>
      {empty ? (
        <Empty compact icon="deals" art={art} title={empty}>
          {emptyNote}
        </Empty>
      ) : (
        <>
          <p className="mt-2 flex flex-wrap items-baseline gap-x-2">
            <span className="text-[1.5rem] leading-tight font-semibold text-ink tabular-nums">{value}</span>
            <span className="text-sm text-ink-2">{label}</span>
          </p>
          <div className="mt-4">{children}</div>
        </>
      )}
    </Sheet>
  );
}
