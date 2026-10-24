import Link from "next/link";
import { getCompanyMe, enc, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { Reconcile, StartReconciliation } from "@/src/modules/finance/bank/forms";
import type { BankAccount, Reconciliation, ReconciliationSummary } from "@/src/modules/finance/bank/types";

// Bank reconciliation (app/routers/bank.py in Finance; decided 2026-10-24, from
// Oojeema): each bank statement matched against the books, line by line.

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;
const td = "px-3 py-2 first:pl-5 last:pr-5";

export async function BankPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<{ accounts: BankAccount[]; history: ReconciliationSummary[] }>("/finance/bank/accounts");
  return (
    <>
      <PageHeader title="Bank reconciliation">
        Match each bank statement against the books: tick what the bank shows until the cleared balance equals the statement&apos;s.
      </PageHeader>
      <div className="space-y-5">
        <Sheet className="overflow-x-auto">
          {data.accounts.length === 0 ? (
            <Empty title="No cash or bank accounts" icon="payments">Set the cash and bank accounts under Accounting, Default accounts.</Empty>
          ) : (
            <table className="w-full min-w-[40rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className={`${td} font-semibold`}>Account</th>
                  <th className={`${td} text-right font-semibold`}>In the books</th>
                  <th className={`${td} font-semibold`}>Reconciled to</th>
                  <th className={`${td} font-semibold`} />
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.accounts.map((a) => (
                  <tr key={a.id}>
                    <td className={td}><span className="font-mono text-meta text-ink-2">{a.code}</span> {a.name}</td>
                    <td className={`${td} text-right tabular-nums`}>{fmt.peso(a.bookBalanceCentavos)}</td>
                    <td className={td}>{a.lastReconciled ? `${fmt.dateLabel(a.lastReconciled)} (${fmt.peso(a.lastStatementBalanceCentavos ?? 0)})` : <span className="text-ink-3">Never</span>}</td>
                    <td className={td}>{a.openId && <Link href={`/finance/bank/${a.openId}`} className="font-semibold text-hema hover:underline">Continue</Link>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Sheet>
        {may(me, "bank.reconcile") && data.accounts.length > 0 && (
          <Sheet className="px-5 py-4">
            <SectionTitle icon="payments">Reconcile a statement</SectionTitle>
            <div className="mt-3">
              <StartReconciliation accounts={data.accounts} org={me.org} today={fmt.todayKey()} />
            </div>
          </Sheet>
        )}
        {data.history.length > 0 && (
          <Sheet className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  {["Statement", "Account", "Balance", "Status"].map((h) => <th key={h} className={`${td} font-semibold`}>{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.history.map((r) => (
                  <tr key={r.id}>
                    <td className={td}><Link href={`/finance/bank/${r.id}`} className="text-hema hover:underline">{fmt.dateLabel(r.statementDate)}</Link></td>
                    <td className={td}>{r.account.name}</td>
                    <td className={`${td} tabular-nums`}>{fmt.peso(r.statementBalanceCentavos)}</td>
                    <td className={td}>{r.status === "done" ? `Reconciled by ${r.finishedBy}` : "In progress"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
