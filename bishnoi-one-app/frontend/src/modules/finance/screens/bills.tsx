import { Plus } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/finance/platform/ui/toggle-links";
import { ApiError, enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { BillEditor } from "@/src/modules/finance/bills/editor";
import { DeleteBillDraft, PayBill, RecordBill, RemoveBillPayment, VoidBill } from "@/src/modules/finance/bills/steps";
import type { Bill, BillSetup, Payables } from "@/src/modules/finance/bills/types";

// Supplier bills (app/routers/bills.py in Finance; decided 2026-10-24, BIR
// features from Oojeema): made out to Inventory's suppliers, recorded with their
// input VAT and the tax withheld, paid; voided rather than changed once recorded.

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;
const STATUS = { draft: "Draft", posted: "Recorded", void: "Void" } as const;
const td = "px-3 py-2 first:pl-5 last:pr-5";
const num = "text-right tabular-nums";

export async function BillsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const status = ["draft", "posted", "void"].includes(one(sp.status)) ? one(sp.status) : "";
  const q = one(sp.q);
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (q) query.set("q", q);
  const data = await load<{ items: Bill[]; counts: Record<string, number> }>(`/finance/bills${query.size ? `?${query}` : ""}`);
  const tab = (key: string, label: string) => ({ value: key || "all", label: key ? `${label} (${data.counts[key] ?? 0})` : label, href: `/finance/bills${key ? `?status=${key}` : ""}` });
  return (
    <>
      <PageHeader
        title="Supplier bills"
        actions={
          may(me, "bills.create") && (
            <LinkButton href="/finance/bills/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New bill
            </LinkButton>
          )
        }
      >
        Your suppliers&apos; invoices: what you owe them, the VAT on your purchases, and the tax you withhold from them for the BIR.
      </PageHeader>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ToggleLinks current={status || "all"} options={[tab("", "All"), tab("draft", "Drafts"), tab("posted", "Recorded"), tab("void", "Voided")]} />
        <form action="/finance/bills" className="flex gap-2">
          {status && <input type="hidden" name="status" value={status} />}
          <input name="q" defaultValue={q} placeholder="Supplier or invoice no." className="h-8 w-56 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
          <button type="submit" className="h-8 rounded-[3px] border border-rule-strong bg-sheet px-3 text-meta font-semibold hover:border-control">Find</button>
        </form>
      </div>
      <Sheet className="overflow-x-auto">
        {data.items.length === 0 ? (
          <Empty title="No bills yet" icon="letters">
            Record a supplier&apos;s invoice when it comes in, or start one from a delivery received in Inventory.
          </Empty>
        ) : (
          <table className="w-full min-w-[56rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                {["Bill no.", "Date", "Supplier", "Their invoice", "Status"].map((h) => <th key={h} className={`${td} font-semibold`}>{h}</th>)}
                {["Total", "Withheld", "Balance"].map((h) => <th key={h} className={`${td} font-semibold text-right`}>{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {data.items.map((b) => (
                <tr key={b.id} className={b.status === "void" ? "text-ink-3" : ""}>
                  <td className={td}>
                    <Link href={`/finance/bills/${b.id}`} className="font-mono text-hema hover:underline">{b.no ?? "Draft"}</Link>
                  </td>
                  <td className={td}>{fmt.dateLabel(b.billDate)}</td>
                  <td className={td}>{b.supplier.name}</td>
                  <td className={td}>{b.supplierInvoiceNo}</td>
                  <td className={td}>{STATUS[b.status]}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(b.totalCentavos)}</td>
                  <td className={`${td} ${num}`}>{b.ewtCentavos ? fmt.peso(b.ewtCentavos) : ""}</td>
                  <td className={`${td} ${num}`}>{b.status === "posted" ? fmt.peso(b.balanceCentavos) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>
    </>
  );
}

export async function NewBillPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const setup = await load<BillSetup>("/finance/bills/setup");
  return (
    <>
      <PageHeader title="New bill" crumbs={[{ href: "/finance/bills", label: "Supplier bills" }]}>
        A supplier&apos;s invoice, as a draft: the input VAT and the tax withheld are worked out when it&apos;s saved. Record it from its page.
      </PageHeader>
      <BillEditor bill={null} setup={setup} org={me.org} today={fmt.todayKey()} />
    </>
  );
}

export async function BillPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  let bill: Bill;
  try {
    bill = await load<Bill>(`/finance/bills/${enc(id)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const title = bill.no ? `Bill ${bill.no}` : "Draft bill";
  if (bill.status === "draft" && may(me, "bills.create")) {
    const setup = await load<BillSetup>("/finance/bills/setup");
    return (
      <>
        <PageHeader title={title} crumbs={[{ href: "/finance/bills", label: "Supplier bills" }]} actions={<DeleteBillDraft id={bill.id} />}>
          {bill.supplier.name}, their invoice {bill.supplierInvoiceNo}. A draft: change it here, then record it.
        </PageHeader>
        {may(me, "bills.record") && (
          <Sheet className="mb-5 px-5 py-4">
            <RecordBill id={bill.id} />
          </Sheet>
        )}
        <BillEditor bill={bill} setup={setup} org={me.org} today={fmt.todayKey()} />
      </>
    );
  }
  const c = bill.computed!;
  return (
    <>
      <PageHeader title={title} crumbs={[{ href: "/finance/bills", label: "Supplier bills" }]}>
        {bill.supplier.name} · their invoice {bill.supplierInvoiceNo} of {fmt.dateLabel(bill.billDate)} · {STATUS[bill.status]}
        {bill.status === "void" && bill.voidReason ? ` (${bill.voidReason})` : ""}
      </PageHeader>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
        <Sheet className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                {["Description", "Account", "VAT"].map((h) => <th key={h} className={`${td} font-semibold`}>{h}</th>)}
                {["Net", "VAT", "Withheld on"].map((h) => <th key={h} className={`${td} font-semibold text-right`}>{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {c.lines.map((l, i) => (
                <tr key={i}>
                  <td className={td}>{l.description}</td>
                  <td className={td}>{l.account ? `${l.account.code} ${l.account.name}` : ""}</td>
                  <td className={td}>{{ vatable: "VATable", zero_rated: "Zero-rated", exempt: "Exempt", non_vat: "Non-VAT" }[l.kind] ?? l.kind}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(l.netCentavos)}</td>
                  <td className={`${td} ${num}`}>{l.vatCentavos ? fmt.peso(l.vatCentavos) : ""}</td>
                  <td className={`${td} ${num}`}>{l.withheld ? "Yes" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Sheet>
        <Sheet className="px-5 py-4">
          <dl className="space-y-1.5 text-sm tabular-nums">
            <div className="flex justify-between"><dt className="text-ink-2">Supplier TIN</dt><dd>{bill.supplier.tin ?? "None"}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-2">Due</dt><dd>{fmt.dateLabel(bill.dueDate)}</dd></div>
            {bill.deliveryRef && <div className="flex justify-between"><dt className="text-ink-2">Delivery</dt><dd>{bill.deliveryRef}</dd></div>}
            <div className="flex justify-between border-t border-rule pt-1.5"><dt className="text-ink-2">Net of VAT</dt><dd>{fmt.peso(c.netCentavos)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-2">Input VAT</dt><dd>{fmt.peso(bill.inputTaxCentavos)}</dd></div>
            <div className="flex justify-between font-semibold"><dt>Invoice total</dt><dd>{fmt.peso(bill.totalCentavos)}</dd></div>
            {bill.atc && (
              <div className="flex justify-between"><dt className="text-ink-2">Withheld, {bill.atc} at {bill.ewtRateBp / 100}% of {fmt.peso(c.ewtBaseCentavos)}</dt><dd>− {fmt.peso(bill.ewtCentavos)}</dd></div>
            )}
            <div className="flex justify-between border-t border-ink pt-1.5 font-semibold"><dt>To pay the supplier</dt><dd>{fmt.peso(bill.payableCentavos)}</dd></div>
            {bill.status === "posted" && <div className="flex justify-between"><dt className="text-ink-2">Still owed</dt><dd>{fmt.peso(bill.balanceCentavos)}</dd></div>}
          </dl>
          {bill.atc && bill.status === "posted" && (
            <p className="mt-3 text-meta text-ink-3">
              The supplier gets a Form 2307 for the quarter:{" "}
              <Link href={`/finance/bir/withholding?form=2307&supplierId=${enc(bill.supplier.id)}`} className="text-hema hover:underline">
                see it under BIR reports
              </Link>
              .
            </p>
          )}
        </Sheet>
      </div>
      {bill.status === "posted" && (
        <Sheet className="mt-5 px-5 py-4">
          <SectionTitle icon="payments">
            Payments <span className="font-normal text-ink-3">· {fmt.peso(bill.paidCentavos)} paid, {fmt.peso(bill.balanceCentavos)} owed</span>
          </SectionTitle>
          {(bill.payments ?? []).length > 0 && (
            <ul className="mb-3 divide-y divide-rule">
              {bill.payments!.map((p) => (
                <li key={p.id} className={`flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm ${p.removedAt ? "text-ink-3 line-through" : ""}`}>
                  <span className="w-28">{fmt.dateLabel(p.paidOn)}</span>
                  <span className="w-32 tabular-nums">{fmt.peso(p.amountCentavos)}</span>
                  <span className="min-w-0 flex-1">
                    {p.methodLabel}
                    {p.reference && <span className="text-ink-3"> · {p.reference}</span>}
                    <span className="text-ink-3"> · {p.recordedBy}</span>
                  </span>
                  {p.removedAt ? <span className="text-meta no-underline">Reversed by {p.removedBy}</span> : may(me, "bills.void") && <RemoveBillPayment id={bill.id} paymentId={p.id} />}
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-start gap-3">
            {bill.balanceCentavos > 0 ? (
              may(me, "bills.pay") && <PayBill id={bill.id} owed={bill.balanceCentavos} methods={bill.methods ?? []} org={me.org} today={fmt.todayKey()} />
            ) : (
              <p className="text-sm text-ink-2">Paid in full.</p>
            )}
            {may(me, "bills.void") && bill.paidCentavos === 0 && <VoidBill id={bill.id} label={`bill ${bill.no}`} />}
          </div>
        </Sheet>
      )}
    </>
  );
}

export async function PayablesPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<Payables>("/finance/bills/payables");
  return (
    <>
      <PageHeader title="Payables">What you owe each supplier on recorded bills, by how late it is, as of {fmt.dateLabel(data.asOf)}.</PageHeader>
      <Sheet className="overflow-x-auto">
        {data.items.length === 0 ? (
          <Empty title="Nothing owed to suppliers" icon="payments" />
        ) : (
          <table className="w-full min-w-[52rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className={`${td} font-semibold`}>Supplier</th>
                {data.buckets.map((b) => <th key={b.key} className={`${td} font-semibold text-right`}>{b.label}</th>)}
                <th className={`${td} font-semibold text-right`}>Owed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {data.items.map((r) => (
                <tr key={r.supplier.id}>
                  <td className={td}>
                    <Link href={`/finance/bills?q=${enc(r.supplier.name)}&status=posted`} className="hover:text-hema hover:underline">{r.supplier.name}</Link>
                  </td>
                  {data.buckets.map((b) => <td key={b.key} className={`${td} ${num} ${b.key !== "current" && Number(r[b.key]) > 0 ? "text-danger" : ""}`}>{Number(r[b.key]) ? fmt.peso(Number(r[b.key])) : ""}</td>)}
                  <td className={`${td} ${num} font-semibold`}>{fmt.peso(r.owedCentavos)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-ink font-semibold tabular-nums">
                <td className={td}>Total</td>
                {data.buckets.map((b) => <td key={b.key} className={`${td} ${num}`}>{fmt.peso(data.totals[b.key] ?? 0)}</td>)}
                <td className={`${td} ${num}`}>{fmt.peso(data.totals.owedCentavos ?? 0)}</td>
              </tr>
            </tfoot>
          </table>
        )}
      </Sheet>
    </>
  );
}
