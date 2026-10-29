import Link from "next/link";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import type { Aging } from "@/src/modules/finance/payables/work-types";

type Search = Promise<Record<string, string | string[] | undefined>>;
export default async function PayablesAging({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["bucket", "supplierId", "asOf"]) if (typeof sp[key] === "string" && sp[key]) query.set(key, sp[key]);
  const past = query.has("asOf");
  const data = await load<Aging>(`/finance/payables/aging?${query}`);
  const billLink = (supplierId?: string, bucket?: string) => {
    const q = new URLSearchParams();
    if (supplierId) q.set("supplierId", supplierId);
    if (bucket) q.set("bucket", bucket);
    q.set("queue", "outstanding");
    return `/finance/bills?${q}`;
  };
  const cell = "px-3 py-3 text-right tabular-nums";
  return <>
    <PageHeader title="Accounts payable aging" actions={<LinkButton href={`/finance/bills/aging/download?${query}`}>Download CSV</LinkButton>}>
      Unpaid supplier bills as of the end of {fmt.dateLabel(data.on)}, grouped by how late they were then. Amounts are after withholding. An earlier day is rebuilt from the dates bills, payments and voids were posted, so it agrees with the books on that day.
    </PageHeader>
    {/* An earlier day, e.g. a month-end to compare with Oojeema's aging report (2026-10-29). */}
    <form method="get" className="mb-4 flex flex-wrap items-end gap-3">
      {query.has("supplierId") && <input type="hidden" name="supplierId" value={query.get("supplierId")!} />}
      {query.has("bucket") && <input type="hidden" name="bucket" value={query.get("bucket")!} />}
      <label className="text-sm">As of<input suppressHydrationWarning type="date" name="asOf" defaultValue={data.on} className="mt-1 block rounded-lg border border-rule bg-sheet px-3 py-2" /></label>
      <button suppressHydrationWarning type="submit" className="rounded-lg border border-rule px-3 py-2 text-sm hover:bg-mint-2">Show</button>
      {past && <Link href="/finance/bills/aging" className="pb-2 text-sm text-hema hover:underline">Back to today</Link>}
    </form>
    <p className="mb-4 text-sm text-ink-2">{data.billCount} bills · {data.suppliers.length} suppliers · Owed: <strong>{fmt.peso(data.totals.owedCentavos)}</strong> · In unreleased vouchers: {fmt.peso(data.totals.reservedCentavos)} · Available to prepare: {fmt.peso(data.totals.availableCentavos)}</p>
    <p className="mb-4 text-meta text-ink-3">{past ? "For an earlier day, money in unreleased vouchers shows as nothing: that's today's state, not that day's." : "Reservations remain part of what is owed until payment is released."} Pending approvals are excluded; a voided bill counts until the day it was voided.</p>
    {query.size > 0 && <p className="mb-3 text-sm"><Link href="/finance/bills/aging" className="text-hema hover:underline">Clear aging filters</Link> · Showing {data.buckets.find((b) => b.key === query.get("bucket"))?.label ?? "all buckets"}{query.has("supplierId") ? " for the selected supplier" : ""}.</p>}
    <Sheet>
      {data.suppliers.length === 0 ? <Empty title="No unpaid bills in this view" icon="lists">Posted bills with an amount left to pay appear here.</Empty> : <div className="overflow-x-auto">
        <table className="w-full min-w-[85rem] text-sm">
          <caption className="sr-only">Supplier balances and unreleased payment reservations on {data.on}</caption>
          <thead><tr className="border-b border-rule text-left">
            <th scope="col" className="px-3 py-3">Supplier / oldest bill</th>
            {data.buckets.map((b) => <th scope="col" key={b.key} className={cell}>{b.label}</th>)}
            {["Owed", "In unreleased vouchers", "Available to prepare"].map((h) => <th scope="col" key={h} className={cell}>{h}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-rule">{data.suppliers.map((s) => <tr key={s.id}>
            <th scope="row" className="px-3 py-3 text-left font-normal">
              <Link href={billLink(s.id, query.get("bucket") ?? undefined)} className="font-semibold text-hema hover:underline">{s.name}</Link>
              <span className="block text-meta text-ink-3">{s.bills.length} bills · oldest {s.oldestDaysLate} days late</span>
              {s.bills[0] && <Link href={`/finance/bills/${s.bills[0].id}`} className="text-meta text-hema hover:underline">Bill {s.bills[0].no} · due {fmt.dateLabel(s.bills[0].dueDate)}</Link>}
            </th>
            {data.buckets.map((b) => <td key={b.key} className={cell}><Link aria-label={`${s.name}, ${b.label}`} href={billLink(s.id, b.key)} className="text-hema hover:underline">{fmt.peso(s.buckets[b.key])}</Link></td>)}
            <td className={cell}><Link href={billLink(s.id, query.get("bucket") ?? undefined)} className="text-hema hover:underline">{fmt.peso(s.owedCentavos)}</Link></td>
            <td className={cell}>{fmt.peso(s.reservedCentavos)}</td><td className={cell}>{fmt.peso(s.availableCentavos)}</td>
          </tr>)}</tbody>
          <tfoot><tr className="border-t-2 border-ink font-semibold"><th scope="row" className="px-3 py-3 text-left">Total</th>
            {data.buckets.map((b) => <td key={b.key} className={cell}>{fmt.peso(b.amountCentavos)}</td>)}
            <td className={cell}>{fmt.peso(data.totals.owedCentavos)}</td><td className={cell}>{fmt.peso(data.totals.reservedCentavos)}</td><td className={cell}>{fmt.peso(data.totals.availableCentavos)}</td>
          </tr></tfoot>
        </table>
      </div>}
    </Sheet>
  </>;
}
