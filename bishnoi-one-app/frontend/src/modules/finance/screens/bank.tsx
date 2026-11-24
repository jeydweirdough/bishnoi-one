import Link from "next/link";
import { getCompanyMe, enc, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { Reconcile, StartReconciliation } from "@/src/modules/finance/bank/forms";
import type { BankAccount, Reconciliation, ReconciliationSummary } from "@/src/modules/finance/bank/types";

// Bank reconciliation (app/routers/bank.py in Finance; decided 2026-10-24, from
// Oojeema): each bank statement matched against the books, line by line.

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;
const td = "px-3 py-2.5 first:pl-5 last:pr-5";

export async function BankPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<{ accounts: BankAccount[]; history: ReconciliationSummary[] }>("/finance/bank/accounts");
  return (
    <>
      <PageHeader title="Bank reconciliation">
        Match each bank statement against the books: tick what the bank shows until the cleared balance equals the statement&apos;s.
      </PageHeader>
      <div className="space-y-4">
        {may(me, "bank.reconcile") && data.accounts.length > 0 && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="payments">Reconcile a statement</SectionTitle>
            <div className="mt-3">
              <StartReconciliation accounts={data.accounts} org={me.org} today={fmt.todayKey()} />
            </div>
          </Sheet>
        )}
        <Sheet className="min-w-0 max-w-full">
          {data.accounts.length === 0 ? (
            <Empty title="No cash or bank accounts" icon="payments">Set the cash and bank accounts under Accounting, Default accounts.</Empty>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-5 py-3">
                <h2 className="text-sm font-semibold text-ink">Cash and bank accounts ({data.accounts.length})</h2>
                <span className="text-meta text-ink-3">Click an account to inspect its ledger entries</span>
              </div>
              <div role="region" aria-label="Cash and bank accounts" tabIndex={0} className="max-h-[52vh] max-w-full overflow-auto overscroll-contain rounded-b-xl focus-visible:outline-2 focus-visible:outline-hema print:max-h-none print:overflow-visible">
                <table className="w-full min-w-[40rem] text-sm">
                  <thead className="sticky top-0 z-10 bg-sheet shadow-[0_1px_0_0_var(--color-rule)] print:static">
                    <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                      <th className={`${td} font-semibold`}>Account</th>
                      <th className={`${td} text-right font-semibold`}>In the books</th>
                      <th className={`${td} font-semibold`}>Reconciled to</th>
                      <th className={`${td} font-semibold`} />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule">
                    {data.accounts.map((a) => (
                      <tr key={a.id} className="transition-colors hover:bg-bench/30">
                        <td className={td}>
                          <Link href={`/finance/ledger/accounts/${a.id}`} className="hover:text-hema hover:underline">
                            <span className="font-mono text-meta text-ink-2">{a.code}</span> <span className="font-medium">{a.name}</span>
                          </Link>
                        </td>
                        <td className={`${td} text-right font-medium tabular-nums ${a.bookBalanceCentavos < 0 ? "text-danger" : ""}`}>{fmt.peso(a.bookBalanceCentavos)}</td>
                        <td className={td}>{a.lastReconciled ? `${fmt.dateLabel(a.lastReconciled)} (${fmt.peso(a.lastStatementBalanceCentavos ?? 0)})` : <span className="text-ink-3">Never</span>}</td>
                        <td className={td}>{a.openId && <Link href={`/finance/bank/${a.openId}`} className="font-semibold text-hema hover:underline">Continue</Link>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Sheet>
        {data.history.length > 0 && (
          <Sheet className="min-w-0 max-w-full">
            <div className="border-b border-rule px-5 py-3">
              <h2 className="text-sm font-semibold text-ink">Past reconciliations ({data.history.length})</h2>
            </div>
            <div role="region" aria-label="Reconciliation history" tabIndex={0} className="max-h-[40vh] max-w-full overflow-auto overscroll-contain rounded-b-xl focus-visible:outline-2 focus-visible:outline-hema print:max-h-none print:overflow-visible">
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-sheet shadow-[0_1px_0_0_var(--color-rule)] print:static">
                  <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                    {["Statement", "Account", "Balance", "Status"].map((h) => <th key={h} className={`${td} font-semibold`}>{h}</th>)}
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {data.history.map((r) => (
                    <tr key={r.id} className="transition-colors hover:bg-bench/30">
                      <td className={td}><Link href={`/finance/bank/${r.id}`} className="font-medium text-hema hover:underline">{fmt.dateLabel(r.statementDate)}</Link></td>
                      <td className={td}>{r.account.name}</td>
                      <td className={`${td} tabular-nums`}>{fmt.peso(r.statementBalanceCentavos)}</td>
                      <td className={td}>{r.status === "done" ? `Reconciled by ${r.finishedBy}` : "In progress"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Sheet>
        )}
      </div>
    </>
  );
}

export async function ReconciliationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const rec = await load<Reconciliation>(`/finance/bank/reconciliations/${enc(id)}`);
  return (
    <>
      <PageHeader title={`${rec.account.name}: statement of ${fmt.dateLabel(rec.statementDate)}`} crumbs={[{ href: "/finance/bank", label: "Bank reconciliation" }]}>
        {rec.status === "done" ? `Reconciled by ${rec.finishedBy}: the lines below are the ones it cleared.` : "Tick each line the bank statement shows."}
      </PageHeader>
      <Reconcile rec={rec} org={me.org} canReconcile={may(me, "bank.reconcile")} />
    </>
  );
}
