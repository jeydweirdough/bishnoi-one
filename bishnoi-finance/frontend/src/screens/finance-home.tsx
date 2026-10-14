import Link from "next/link";
import { Figure } from "@/src/platform/ui/figure";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { FundCounts } from "../funds/types";
import type { Posting, TrialBalance } from "../ledger/types";

// Finance's overview: what's waiting on Finance, and the balances that matter
// for cash advances, as the ledger has them today.

export const metadata = { title: "Overview" };

export default async function FinanceHome() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [counts, tb, posting] = await Promise.all([
    load<FundCounts & { to_settle: number }>("/finance/funds/counts"),
    load<TrialBalance>("/finance/ledger/trial-balance"),
    load<Posting>("/finance/ledger/posting"),
  ]);
  const balanceOf = (id: string | undefined) => tb.rows.find((r) => r.account.id === id)?.balanceCentavos ?? 0;
  const account = (key: string) => posting.items.find((i) => i.key === key)?.account ?? null;
  // Each money account once: check payments may post to the bank account.
  const money = [...new Map(["cash_account_id", "bank_account_id", "ewallet_account_id", "check_account_id"].map((k) => account(k)).filter((a) => a !== null).map((a) => [a!.id, a!])).values()];
  const advances = account("advances_account_id");
  const payable = account("due_to_employees_account_id");

  return (
    <>
      <PageHeader title="Overview">{me.user.fullName}, here is what needs Finance&apos;s action today.</PageHeader>
      <div className="space-y-5">
        <Sheet>
          <div className="px-5 pt-4">
            <SectionTitle icon="payments">Marketing requests</SectionTitle>
          </div>
          <div className="grid grid-cols-2 divide-x divide-rule sm:grid-cols-4">
            <Figure label="For release" value={counts.to_release} href="/funds" />
            <Figure label="For review" value={counts.to_check} href="/funds/review" />
            <Figure label="For settlement" value={counts.to_settle} href="/funds/settlement" />
            <Figure label="Overdue liquidations" value={counts.overdue} href="/funds/outstanding" flag />
          </div>
        </Sheet>

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
      </div>
    </>
  );
}
