import Link from "next/link";
import { Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { Format } from "@/src/platform/lib/format";
import type { SalesResults } from "@/src/platform/lib/types";
import { TargetProgress } from "./target-progress";

/** This month's won revenue against the target, for a home page: one's own, or the team's. */
export async function MonthTarget({ view, fmt, today, mayTarget }: { view: "mine" | "team"; fmt: Format; today: string; mayTarget: boolean }) {
  const r = await load<SalesResults>(`/sales/results?view=${view}`);
  const results = `/deals?view=results${view === "mine" ? "&who=me" : ""}`;
  return (
    <Sheet className="mb-5 px-5 py-4">
      <TargetProgress
        figures={r.totals}
        start={r.start}
        end={r.end}
        today={today}
        fmt={fmt}
        label={`${view === "team" ? "Your team's sales" : "Your sales"} in ${r.label}`}
        href={mayTarget ? `/deals/targets?month=${r.period}` : undefined}
      />
      <p className="mt-2 text-meta">
        <Link href={results} className="text-hema hover:underline">
          See sales results
        </Link>
      </p>
    </Sheet>
  );
}
