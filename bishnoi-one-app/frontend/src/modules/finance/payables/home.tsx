import Link from "next/link";
import { load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import type { PayablesWork } from "./work-types";

export async function PayablesHome({ org }: { org: Org }) {
  const data = await load<PayablesWork>("/finance/dashboard/payables");
  const fmt = makeFormat(org);
  const groups = [...new Set(data.queues.map((q) => q.group))];
  return <Sheet className="px-5 py-4">
    <SectionTitle icon="payments">Payables</SectionTitle>
    <p className="mb-4 text-meta text-ink-3">Current work and balances · {fmt.dateLabel(data.on)}. Task groups can contain the same bill; do not add their amounts together.</p>
    {groups.length === 0 && <p className="text-sm text-ink-2">No Payables tasks waiting for you.</p>}
    <div className="grid gap-5 lg:grid-cols-2">
      {groups.map((group) => <section key={group}>
        <h3 className="mb-2 text-sm font-semibold">{group}</h3>
        <ul className="divide-y divide-rule text-sm">
          {data.queues.filter((q) => q.group === group).map((q) => <li key={q.key} className="py-2">
            <Link href={q.href} className="flex flex-wrap justify-between gap-2 text-hema hover:underline">
              <span>{q.label} · {q.count} {q.unit}</span><span className="tabular-nums">{fmt.peso(q.amountCentavos)}</span>
            </Link>
            {q.reservedCentavos > 0 && <p className="text-meta text-ink-3">In unreleased vouchers: {fmt.peso(q.reservedCentavos)} · Available to prepare: {fmt.peso(q.availableCentavos)}</p>}
            {(q.key.includes("returned") || q.key.includes("sent_")) && <ul className="mt-1 space-y-1 text-meta text-ink-2">
              {q.details.map((d) => <li key={d.id}><Link href={d.href} className="hover:text-hema hover:underline">{d.label}</Link>{d.note && <> · {d.note}</>}</li>)}
              {q.count > q.details.length && <li>Showing the first {q.details.length}; open the queue for all {q.count}.</li>}
            </ul>}
          </li>)}
        </ul>
      </section>)}
    </div>
    {data.aging && <section className="mt-5 border-t border-rule pt-4">
      <Link href="/finance/bills/aging" className="font-semibold text-hema hover:underline">Owed to suppliers · {fmt.peso(data.aging.totals.owedCentavos)}</Link>
      <p className="mt-1 text-meta text-ink-2">{data.aging.billCount} unpaid bills · In unreleased vouchers: {fmt.peso(data.aging.totals.reservedCentavos)} · Available to prepare: {fmt.peso(data.aging.totals.availableCentavos)}</p>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {data.aging.buckets.map((b) => <Link key={b.key} href={`/finance/bills/aging?bucket=${b.key}`} className="hover:text-hema hover:underline">{b.label}: <span className="tabular-nums">{fmt.peso(b.amountCentavos)}</span></Link>)}
      </div>
      <p className="mt-2 text-meta text-ink-3">Only posted bills are owed. Drafts and bills awaiting approval or a tax check are excluded. An unreleased voucher reserves money; it does not pay the bill.</p>
    </section>}
  </Sheet>;
}
