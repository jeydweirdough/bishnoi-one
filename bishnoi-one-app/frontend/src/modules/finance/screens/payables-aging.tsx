import Link from "next/link";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Amount } from "@/src/modules/finance/platform/ui/amount";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import type { Aging } from "@/src/modules/finance/payables/work-types";

const BUCKET_TONES: Record<string, string> = {
  current: "bg-due-later",
  "1_30": "bg-due-today",
  "31_60": "bg-danger/60",
  "61_90": "bg-danger/80",
  over_90: "bg-danger",
};

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
  const cell = "px-4 py-3.5 text-right tabular-nums whitespace-nowrap";
  const currentBucket = data.buckets.find((b) => b.key === "current")?.amountCentavos ?? 0;
  const lateCentavos = Math.max(0, data.totals.owedCentavos - currentBucket);
  return <>
    <PageHeader title="Accounts payable aging" actions={<LinkButton href={`/finance/bills/aging/download?${query}`}>Download CSV</LinkButton>}>
      Unpaid supplier bills as of the end of {fmt.dateLabel(data.on)}, grouped by how late they were then. Amounts are after withholding. An earlier day is rebuilt from the dates bills, payments and voids were posted, so it agrees with the books on that day.
    </PageHeader>

    <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
      <Sheet className="px-4 py-3.5 lg:col-span-1">
        <p className="text-meta text-ink-3">Total owed ({data.billCount} bills)</p>
        <p className="mt-0.5 text-figure tabular-nums"><Amount text={fmt.peso(data.totals.owedCentavos)} /></p>
        <p className={`mt-0.5 text-meta ${lateCentavos > 0 ? "text-danger" : "text-ink-3"}`}>
          {lateCentavos > 0 ? `${fmt.peso(lateCentavos)} past due` : "Nothing past due"}
        </p>
      </Sheet>
      {data.buckets.map((b) => (
        <Sheet key={b.key} className="px-4 py-3.5">
          <p className="flex items-center gap-1.5 text-meta text-ink-3">
            <span className={`inline-block size-2 rounded-full ${BUCKET_TONES[b.key] ?? "bg-danger"}`} aria-hidden />
            {b.label}
          </p>
          <p className="mt-1 text-heading tabular-nums">{fmt.peso(b.amountCentavos)}</p>
        </Sheet>
      ))}
    </div>

    {data.totals.owedCentavos > 0 && (
      <div className="mb-5 flex h-2.5 overflow-hidden rounded-full bg-bench" role="img" aria-label={data.buckets.map((b) => `${b.label}: ${fmt.peso(b.amountCentavos)}`).join(", ")}>
        {data.buckets.map((b) => (b.amountCentavos ? <span key={b.key} className={BUCKET_TONES[b.key] ?? "bg-danger"} style={{ width: `${(b.amountCentavos / data.totals.owedCentavos) * 100}%` }} /> : null))}
      </div>
    )}

    <div className="mb-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-rule bg-sheet px-4 py-3">
      <form method="get" className="flex flex-wrap items-center gap-3">
        {query.has("supplierId") && <input type="hidden" name="supplierId" value={query.get("supplierId")!} />}
        {query.has("bucket") && <input type="hidden" name="bucket" value={query.get("bucket")!} />}
        <label className="flex items-center gap-2 text-meta font-medium text-ink-2">
          As of
          <input suppressHydrationWarning type="date" name="asOf" defaultValue={data.on} className="h-8 rounded-lg border border-rule-strong bg-sheet px-2.5 text-sm text-ink" />
        </label>
        <button suppressHydrationWarning type="submit" className="h-8 rounded-lg border border-rule-strong bg-sheet px-3 text-meta font-semibold text-ink hover:border-control">Show</button>
        {past && <Link href="/finance/bills/aging" className="text-meta font-semibold text-hema hover:underline">Back to today</Link>}
      </form>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-meta text-ink-2">
        <span><strong>{data.suppliers.length}</strong> suppliers</span>
        <span>·</span>
        <span>In unreleased vouchers: <strong className="text-ink tabular-nums">{fmt.peso(data.totals.reservedCentavos)}</strong></span>
        <span>·</span>
        <span>Available to prepare: <strong className="text-hema tabular-nums">{fmt.peso(data.totals.availableCentavos)}</strong></span>
      </div>
    </div>

    <p className="mb-3 text-meta text-ink-3">{past ? "For an earlier day, money in unreleased vouchers shows as nothing: that's today's state, not that day's." : "Reservations remain part of what is owed until payment is released."} Pending approvals are excluded; a voided bill counts until the day it was voided.</p>
    {query.size > 0 && <p className="mb-3 text-sm"><Link href="/finance/bills/aging" className="font-semibold text-hema hover:underline">Clear aging filters</Link> · Showing {data.buckets.find((b) => b.key === query.get("bucket"))?.label ?? "all buckets"}{query.has("supplierId") ? " for the selected supplier" : ""}.</p>}
    <Sheet className="min-w-0 max-w-full">
      {data.suppliers.length === 0 ? <Empty title="No unpaid bills in this view" icon="lists">Posted bills with an amount left to pay appear here.</Empty> : <div role="region" aria-label="Accounts payable aging table" tabIndex={0} className="max-h-[60vh] max-w-full overflow-auto overscroll-contain rounded-xl focus-visible:outline-2 focus-visible:outline-hema print:max-h-none print:overflow-visible">
        <table className="w-full min-w-[76rem] text-sm">
          <caption className="sr-only">Supplier balances and unreleased payment reservations on {data.on}</caption>
          <thead className="sticky top-0 z-10 bg-sheet shadow-[0_1px_0_0_var(--color-rule)] print:static"><tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            <th scope="col" className="py-3 pr-4 pl-5 font-semibold">Supplier / oldest bill</th>
            {data.buckets.map((b) => <th scope="col" key={b.key} className={`${cell} font-semibold`}>{b.label}</th>)}
            {["Owed", "In unreleased vouchers", "Available to prepare"].map((h) => <th scope="col" key={h} className={`${cell} font-semibold last:pr-5`}>{h}</th>)}
          </tr></thead>
          <tbody className="divide-y divide-rule">{data.suppliers.map((s) => <tr key={s.id} className="align-top transition-colors hover:bg-bench/30">
            <th scope="row" className="py-3.5 pr-4 pl-5 text-left font-normal">
              <Link href={billLink(s.id, query.get("bucket") ?? undefined)} className="font-semibold text-ink hover:text-hema hover:underline">{s.name}</Link>
              <span className="mt-0.5 block text-meta text-ink-3">{s.bills.length} {s.bills.length === 1 ? "bill" : "bills"} · oldest {s.oldestDaysLate} days late</span>
              {s.bills[0] && <Link href={`/finance/bills/${s.bills[0].id}`} className="mt-0.5 inline-block font-mono text-meta text-hema hover:underline">Bill {s.bills[0].no} · due {fmt.dateLabel(s.bills[0].dueDate)}</Link>}
            </th>
            {data.buckets.map((b) => {
              const val = s.buckets[b.key];
              return <td key={b.key} className={cell}>
                <Link aria-label={`${s.name}, ${b.label}`} href={billLink(s.id, b.key)} className={val ? (b.key !== "current" ? "font-medium text-danger hover:underline" : "font-medium text-hema hover:underline") : "text-ink-3/60 hover:underline"}>
                  {fmt.peso(val)}
                </Link>
              </td>;
            })}
            <td className={`${cell} font-semibold`}><Link href={billLink(s.id, query.get("bucket") ?? undefined)} className="text-hema hover:underline">{fmt.peso(s.owedCentavos)}</Link></td>
            <td className={`${cell} ${s.reservedCentavos ? "text-ink" : "text-ink-3/60"}`}>{fmt.peso(s.reservedCentavos)}</td>
            <td className={`${cell} pr-5 font-medium`}>{fmt.peso(s.availableCentavos)}</td>
          </tr>)}</tbody>
          <tfoot className="sticky bottom-0 z-10 bg-sheet shadow-[0_-1px_0_0_var(--color-ink)] print:static"><tr className="border-t-2 border-ink font-semibold"><th scope="row" className="py-3 pr-4 pl-5 text-left">Total</th>
            {data.buckets.map((b) => <td key={b.key} className={cell}>{fmt.peso(b.amountCentavos)}</td>)}
            <td className={cell}>{fmt.peso(data.totals.owedCentavos)}</td><td className={cell}>{fmt.peso(data.totals.reservedCentavos)}</td><td className={`${cell} pr-5`}>{fmt.peso(data.totals.availableCentavos)}</td>
          </tr></tfoot>
        </table>
      </div>}
    </Sheet>
  </>;
}
