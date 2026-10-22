import Link from "next/link";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import type { Posting, TrialBalance } from "../ledger/types";

/** The money accounts' balances, and what's out with employees, as the ledger
 *  has them today. The Overview has always shown these; the dashboard too. */
export async function CashBalances({ org }: { org: Org }) {
  const fmt = makeFormat(org);
  const [tb, posting] = await Promise.all([load<TrialBalance>("/finance/ledger/trial-balance"), load<Posting>("/finance/ledger/posting")]);
  const balanceOf = (id: string | undefined) => tb.rows.find((r) => r.account.id === id)?.balanceCentavos ?? 0;
  const account = (key: string) => posting.items.find((i) => i.key === key)?.account ?? null;
  // Each money account once: check payments may post to the bank account.
  const money = [...new Map(["cash_account_id", "bank_account_id", "ewallet_account_id", "check_account_id"].map((k) => account(k)).filter((a) => a !== null).map((a) => [a!.id, a!])).values()];
  const advances = account("advances_account_id");
  const payable = account("due_to_employees_account_id");

  return (
    <Sheet className="px-5 py-4">
      <SectionTitle icon="lists">Balances as of {fmt.dateLabel(tb.to)}</SectionTitle>
      <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        {[
          ...money.map((a) => [a, "Cash and cash equivalents"] as const),
          ...(advances ? [[advances, "Cash advances not yet liquidated or refunded"] as const] : []),
          ...(payable ? [[payable, "Reimbursements payable to employees"] as const] : []),
        ].map(([a, hint]) => (
          <div key={a.id} className="flex items-baseline justify-between gap-4 border-b border-rule py-1.5">
            <dt>
              <Link href={`/ledger/accounts/${a.id}`} className="hover:text-hema hover:underline">
                {a.code} · {a.name}
              </Link>
              <span className="block text-meta text-ink-3">{hint}</span>
            </dt>
            <dd className="font-semibold tabular-nums">{fmt.peso(balanceOf(a.id))}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-meta text-ink-3">
        From the ledger. See the <Link href="/ledger/trial-balance" className="text-hema hover:underline">trial balance</Link> for every account.
      </p>
    </Sheet>
  );
}
