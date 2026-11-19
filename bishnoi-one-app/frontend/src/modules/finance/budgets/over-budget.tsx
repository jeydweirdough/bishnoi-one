import { Alert } from "@/src/modules/finance/platform/ui/alert";
import type { makeFormat } from "@/src/modules/finance/platform/lib/format";

// Over-budget warning (Sir Mel, recording 12): shown on a bill or petty cash voucher that isn't
// posted yet, when the month's spending on an account would pass its budget. A warning only:
// the API works it out (app/budget_watch.py) and never blocks the next step.
export type OverBudget = {
  accountId: string;
  code: string;
  account: string;
  month: string; // YYYY-MM
  budgetCentavos: number;
  postedCentavos: number;
  thisCentavos: number;
  overCentavos: number;
};

const monthName = (m: string) =>
  new Intl.DateTimeFormat("en-PH", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${m}-01T12:00:00Z`));

export function OverBudgetNotice({ rows, fmt, className = "mb-5" }: { rows: OverBudget[]; fmt: ReturnType<typeof makeFormat>; className?: string }) {
  if (!rows.length) return null;
  return (
    <Alert tone="warn" className={className} title={rows.length === 1 ? "Over budget" : `Over budget on ${rows.length} accounts`}>
      <ul className="space-y-1">
        {rows.map((r) => (
          <li key={r.accountId}>
            <span className="font-semibold">{r.code} {r.account}</span>, {monthName(r.month)}: budget {fmt.peso(r.budgetCentavos)}, already
            spent {fmt.peso(r.postedCentavos)}, this adds {fmt.peso(r.thisCentavos)}.{" "}
            <span className="font-semibold">{fmt.peso(r.overCentavos)} over.</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-ink-2">It can still go ahead; whoever approves it decides.</p>
    </Alert>
  );
}
