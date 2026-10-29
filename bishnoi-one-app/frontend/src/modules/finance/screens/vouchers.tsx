import { Plus, Printer } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { PrintButton } from "@/src/modules/finance/invoices/steps";
import { AttachedFiles } from "@/src/modules/finance/payables/files";
import { PrintAttachmentSources } from "../printing/attachment-source";
import { SignatureLines } from "@/src/modules/finance/signature/blocks";
import type { SignedStep } from "@/src/modules/finance/signature/types";
import { attachVoucherFile, removeVoucherFile } from "@/src/modules/finance/vouchers/actions";
import { VoucherEditor } from "@/src/modules/finance/vouchers/editor";
import { VoucherSteps } from "@/src/modules/finance/vouchers/steps";
import { ZohoImport } from "@/src/modules/finance/import-matching/zoho-import";
import { VOUCHER_STATUS_LABELS, type Voucher, type VoucherChoices, type VoucherStatus, type VoucherSummary } from "@/src/modules/finance/vouchers/types";

// Payment vouchers (app/routers/vouchers.py; Plans/Plan - Payment vouchers): prepared, then
// released and posted by Cristal; returned with a reason back to whoever prepared it. The checks
// are on the bill (Aubrey's flow, 2026-10-23): only approved bills can be paid. Each tab is
// someone's list of what waits on them.

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

function StatusMark({ status }: { status: VoucherStatus }) {
  const tone =
    status === "released" ? "bg-hema-tint text-hema" : status === "returned" ? "bg-due-today/15 text-due-today" : status === "void" || status === "cancelled" ? "bg-danger-tint text-danger" : "bg-bench text-ink-2";
  return <span className={`rounded-full px-2 py-0.5 text-meta font-medium ${tone}`}>{VOUCHER_STATUS_LABELS[status]}</span>;
}

const TABS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "draft", label: "Drafts" },
  { key: "returned", label: "Returned" },
  { key: "to_release", label: "To release" },
  { key: "released", label: "Released" },
];

export async function VouchersPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const show = one(sp.show);
  const q = one(sp.q);
  const query = new URLSearchParams();
  if (show) query.set("show", show);
  if (q) query.set("q", q);
  if (one(sp.queue)) query.set("queue", one(sp.queue));
  const list = await load<{ items: (VoucherSummary & { queueNote?: string | null })[]; counts: Record<VoucherStatus, number>; canPrepare: boolean; queueLabel: string | null }>(`/finance/vouchers?${query}`);
  // Importing Zoho's supplier payments: its own tick, and the testing site only for now (app/routers/imports.py).
  const canImport = (me.permissions?.includes("imports.run") ?? false) && me.dataEnvironment === "local_test";
  return (
    <>
      <PageHeader
        title="Payment vouchers"
        actions={
          (canImport || list.canPrepare) && (
            <>
              {canImport && <ZohoImport kind="supplier-payments" />}
              {list.canPrepare && (
                <LinkButton href="/finance/vouchers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                  New payment voucher
                </LinkButton>
              )}
            </>
          )
        }
      >
        Paying suppliers&apos; bills once they&apos;re approved: prepared, then released, which posts it. A voucher returned for correction goes back to whoever
        prepared it, with the reason.
      </PageHeader>
      {list.queueLabel && <p className="mb-3 text-sm text-ink-2">{list.queueLabel} · {list.items.length} matching vouchers · <Link href="/finance/vouchers" className="text-hema hover:underline">Clear filters</Link></p>}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Show" className="flex flex-wrap gap-1.5">
          {TABS.map((t) => {
            const n = t.key ? list.counts[t.key as VoucherStatus] : 0;
            return (
              <Link
                key={t.key}
                href={t.key ? `/finance/vouchers?show=${t.key}` : "/finance/vouchers"}
                aria-current={show === t.key ? "page" : undefined}
                className={`rounded-[3px] border px-3 py-1 text-meta ${show === t.key ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:border-control"}`}
              >
                {t.label}
                {n ? <span className={t.key === "returned" ? "font-semibold text-due-today" : "text-ink-3"}> {n}</span> : null}
              </Link>
            );
          })}
        </nav>
        <form className="flex gap-2">
          {query.has("queue") && <input suppressHydrationWarning type="hidden" name="queue" value={query.get("queue")!} />}
          {show && <input suppressHydrationWarning type="hidden" name="show" value={show} />}
          <input suppressHydrationWarning name="q" defaultValue={q} placeholder="Number, supplier, Oojeema PV, check" aria-label="Find a voucher" className="h-8 w-72 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </form>
      </div>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty title={q || show ? "No matching vouchers" : "No payment vouchers yet"} icon="payments">
            {!q && !show && list.canPrepare ? "Prepare the first one with New payment voucher." : null}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="py-2 pr-3 pl-5 font-semibold">Voucher</th>
                  <th className="px-3 py-2 font-semibold">Supplier</th>
                  <th className="px-3 py-2 font-semibold">How</th>
                  <th className="px-3 py-2 font-semibold">Prepared by</th>
                  <th className="px-3 py-2 text-right font-semibold">Amount</th>
                  <th className="py-2 pr-5 pl-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {list.items.map((v) => (
                  <tr key={v.id} className="relative hover:bg-bench/40">
                    <td className="py-2.5 pr-3 pl-5 font-mono text-meta">
                      <Link href={`/finance/vouchers/${v.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {v.number}
                      </Link>
                      {v.oojeemaRef && <span className="block text-ink-3">Oojeema {v.oojeemaRef}</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {v.supplier.name}
                      <span className="block text-meta text-ink-3">
                        {v.bills} {v.bills === 1 ? "bill" : "bills"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-ink-2">
                      {v.methodLabel}
                      {v.paidOn && <span className="block text-meta text-ink-3">Paid {fmt.dateLabel(v.paidOn)}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-ink-2">{v.preparedBy}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{fmt.peso(v.totalCentavos)}</td>
                    <td className="py-2.5 pr-5 pl-3">
                      <StatusMark status={v.status} />
                      {v.queueNote && <span className="mt-1 block text-meta text-ink-2">{v.queueNote}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}

export async function NewVoucherPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const sp = await searchParams;
  const supplier = one(sp.supplier);
  const choices = await load<VoucherChoices>(`/finance/vouchers/choices${supplier ? `?supplier=${enc(supplier)}` : ""}`);
  return (
    <>
      <PageHeader title="New payment voucher" crumbs={[{ href: "/finance/vouchers", label: "Payment vouchers" }]}>
        Pick the supplier and tick the bills it pays: only bills ready to pay (approved, and checked where tax is withheld) are offered. Part of a bill can be
        paid: what&apos;s left stays owed and shows on the bill.
      </PageHeader>
      <VoucherEditor voucher={null} choices={choices} preselect={one(sp.bill) || null} org={me.org} />
    </>
  );
}

const EVENT_LABELS: Record<string, string> = {
  created: "Prepared",
  submitted: "Submitted for release",
  resubmitted: "Corrected and submitted again",
  checked: "Checked",
  returned: "Returned for correction",
  approved: "Approved",
  released: "Released and posted",
  imported: "Imported from a Zoho export (released in Zoho)",
  cancelled: "Cancelled",
  voided: "Voided",
};

export async function VoucherPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const editing = one((await searchParams).edit) === "1";
  const v = await load<Voucher>(`/finance/vouchers/${enc(id)}`);
  const crumbs = [{ href: "/finance/vouchers", label: "Payment vouchers" }];
  const when = fmt.on({ dateStyle: "medium", timeStyle: "short" });

  if (editing && v.canEdit) {
    const choices = await load<VoucherChoices>(`/finance/vouchers/choices?supplier=${enc(v.supplier.id)}&voucher=${enc(v.id)}`);
    return (
      <>
        <PageHeader title={`${v.number} · ${v.supplier.name}`} crumbs={crumbs} />
        <VoucherEditor voucher={v} choices={choices} preselect={null} org={me.org} />
      </>
    );
  }

  const lastReturn = [...v.events].reverse().find((e) => e.kind === "returned");
  return (
    <>
      <PageHeader
        title={`${v.number} · ${v.supplier.name}`}
        crumbs={crumbs}
        actions={
          <>
            {v.canEdit && <LinkButton href={`/finance/vouchers/${v.id}?edit=1`}>Edit</LinkButton>}
            <LinkButton href={`/finance/vouchers/${v.id}/print`} icon={<Printer className="size-4" aria-hidden />}>
              Voucher
            </LinkButton>
          </>
        }
      >
        <StatusMark status={v.status} />
        {v.zohoSync && <p role="status" className="mt-2 text-sm text-ink-2">Zoho: {v.zohoSync.label}. {v.zohoSync.message}</p>}
        <span className="ml-2 text-meta text-ink-2">
          {v.methodLabel} · {fmt.peso(v.totalCentavos)}
          {v.paidFrom && ` from ${v.paidFrom.code} · ${v.paidFrom.name}`}
        </span>
      </PageHeader>

      {v.status === "returned" && lastReturn && (
        <p className="mb-4 rounded-[3px] bg-due-today/10 px-4 py-2 text-sm">
          <span className="font-semibold">Returned for correction</span> by {lastReturn.who}: {lastReturn.text}
        </p>
      )}

      <div className="mb-5">
        {v.lines.map(line => <PrintAttachmentSources key={line.billId} files={line.files} openBase={`/finance/bills/${line.billId}/files`} />)}
        <VoucherSteps voucher={v} today={fmt.todayKey()} />
      </div>

      <Sheet className="px-6 py-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Particulars
            items={[
              ["Pay to", <Link key="s" href={`/finance/suppliers/${v.supplier.id}`} className="text-hema hover:underline">{v.supplier.name}</Link>],
              ["Their bank", [v.supplier.bankName, v.supplier.bankAccountName, v.supplier.bankAccountNumber].filter(Boolean).join(" · ") || null],
              ["Oojeema PV", v.oojeemaRef],
              ["Zoho", v.zohoRef],
            ]}
          />
          <Particulars
            items={[
              ["Prepared by", v.preparedBy],
              ["Released by", v.releasedBy ? `${v.releasedBy}${v.paidOn ? `, ${fmt.dateLabel(v.paidOn)}` : ""}` : null],
              [v.method === "check" ? "Check" : "Bank reference", v.method === "check" ? (v.checkNumber ? `No. ${v.checkNumber}${v.checkDate ? `, ${fmt.dateLabel(v.checkDate)}` : ""}` : null) : v.bankReference],
            ]}
          />
        </div>
        <table className="mt-5 w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-1.5 pr-2 font-semibold">Bill</th>
              <th className="px-2 py-1.5 text-right font-semibold">To pay</th>
              <th className="px-2 py-1.5 text-right font-semibold">Paid before</th>
              <th className="px-2 py-1.5 text-right font-semibold">This voucher</th>
              <th className="py-1.5 pl-2 text-right font-semibold">Left after</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {v.lines.map((l) => (
              <tr key={l.billId} className="align-top">
                <td className="py-2 pr-2">
                  <Link href={`/finance/bills/${l.billId}`} className="font-mono text-meta font-semibold text-hema hover:underline">
                    {l.billNo}
                  </Link>{" "}
                  · their invoice <span className="font-mono text-meta">{l.billNumber}</span>
                  <BillApprovals line={l} />
                  {l.documentMissing ? (
                    <span className="block text-meta text-due-today">Document missing</span>
                  ) : (
                    <span className="block text-meta">
                      {l.files.map((f, i) => (
                        <span key={f.id}>
                          {i > 0 && ", "}
                          <a href={`/finance/bills/${l.billId}/files/${f.id}`} target="_blank" rel="noreferrer" className="text-hema hover:underline">
                            {f.name}
                          </a>
                        </span>
                      ))}
                    </span>
                  )}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">{fmt.peso(l.payableCentavos)}</td>
                <td className="px-2 py-2 text-right tabular-nums text-ink-2">{fmt.peso(l.paidBeforeCentavos)}</td>
                <td className="px-2 py-2 text-right font-semibold tabular-nums">{fmt.peso(l.amountCentavos)}</td>
                <td className="py-2 pl-2 text-right tabular-nums">
                  {fmt.peso(l.leftAfterCentavos)}
                  <span className={`block text-meta ${l.partial ? "font-semibold text-due-today" : "text-hema"}`}>{l.partial ? "Partly paid" : "Paid in full"}</span>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-ink font-semibold">
              <td colSpan={3} className="py-2 text-right">
                Total
              </td>
              <td className="px-2 py-2 text-right tabular-nums">{fmt.peso(v.totalCentavos)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
        <p className="mt-2 text-meta text-ink-2">{v.amountInWords}</p>
        {v.notes && <p className="mt-3 text-meta text-ink-2">{v.notes}</p>}
      </Sheet>

      <Sheet className="mt-5 px-5 py-4">
        <SectionTitle>Proof of payment</SectionTitle>
        <AttachedFiles
          files={v.files}
          openBase={`/finance/vouchers/${v.id}/files`}
          label="Attach proof of payment"
          attach={v.canAttach ? attachVoucherFile.bind(null, v.id) : undefined}
          remove={v.canAttach ? removeVoucherFile.bind(null, v.id) : undefined}
          empty={<p className="text-sm text-ink-3">None yet: the deposit slip, a photo of the check, or the bank&apos;s confirmation can be kept here.</p>}
        />
      </Sheet>

      <Sheet className="mt-5 px-5 py-4">
        <SectionTitle>History</SectionTitle>
        <ul className="divide-y divide-rule text-sm">
          {v.events.map((e, i) => (
            <li key={i} className="grid gap-1 py-2 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
              <span className="text-ink-2 tabular-nums">{when.format(new Date(e.at))}</span>
              <span>
                <span className="font-semibold">{e.who}</span> · {EVENT_LABELS[e.kind] ?? e.kind}
                {e.text && <span className={e.kind === "returned" ? "text-due-today" : "text-ink-2"}>: {e.text}</span>}
              </span>
            </li>
          ))}
        </ul>
      </Sheet>
      {v.entryId && (
        <p className="mt-3 text-meta text-ink-3">
          <Link href="/finance/ledger?source=voucher" className="text-hema hover:underline">
            View journal entry
          </Link>
        </p>
      )}
    </>
  );
}

/** Who approved the bill, and who checked its tax withheld: the checks a voucher relies on. */
function BillApprovals({ line: l }: { line: Voucher["lines"][number] }) {
  if (!l.approvedBy) return null;
  return (
    <span className="block text-meta text-ink-2">
      Approved by {l.approvedBy}
      {l.checkedBy && ` · tax withheld checked by ${l.checkedBy}`}
    </span>
  );
}

/** The voucher as it prints: the bills paid and who approved each, the amount in words, and the e-signatures. */
export async function PrintVoucherPage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const [v, signed] = await Promise.all([load<Voucher>(`/finance/vouchers/${enc(id)}`), load<{ steps: SignedStep[] }>(`/finance/signatures/payment_voucher/${enc(id)}`)]);
  const kind = v.method === "check" ? "Check voucher" : "Payment voucher";
  return (
    <>
      <PrintAttachmentSources files={v.files} openBase={`/finance/vouchers/${v.id}/files`} />
      {v.lines.map(line => <PrintAttachmentSources key={line.billId} files={line.files} openBase={`/finance/bills/${line.billId}/files`} />)}
      <div className="print:hidden">
        <PageHeader crumbs={[{ href: `/finance/vouchers/${v.id}`, label: v.number }]} title={`${kind} ${v.number}`} actions={<PrintButton />}>
          Print it, or choose &quot;Save as PDF&quot; in the print window.
        </PageHeader>
      </div>
      <Sheet className="relative px-8 py-7 print:border-0 print:shadow-none">
        {v.status !== "released" && (
          <p className="mb-4 rounded-[3px] bg-danger-tint px-3 py-2 text-sm font-semibold text-danger">
            {v.status === "void" || v.status === "cancelled" ? `${VOUCHER_STATUS_LABELS[v.status]}: not a payment.` : `${VOUCHER_STATUS_LABELS[v.status]}: not paid yet.`}
          </p>
        )}
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink pb-3">
          <div>
            <p className="finance-document-company-name text-meta text-ink-3 uppercase">{me.org.name}</p>
            <h2 className="text-heading">{kind}</h2>
          </div>
          <dl className="text-right text-sm">
            <div>
              <dt className="inline text-ink-3">No. </dt>
              <dd className="inline font-mono font-semibold">{v.number}</dd>
            </div>
            {v.oojeemaRef && (
              <div>
                <dt className="inline text-ink-3">Oojeema PV </dt>
                <dd className="inline font-mono">{v.oojeemaRef}</dd>
              </div>
            )}
            <div>
              <dt className="inline text-ink-3">Date </dt>
              <dd className="inline">{v.paidOn ? fmt.dateLabel(v.paidOn) : "—"}</dd>
            </div>
          </dl>
        </div>
        <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
          <div>
            <dt className="inline text-ink-3">Pay to: </dt>
            <dd className="inline font-semibold">{v.supplier.companyName ?? v.supplier.name}</dd>
          </div>
          {v.supplier.tin && (
            <div>
              <dt className="inline text-ink-3">TIN: </dt>
              <dd className="inline">
                {v.supplier.tin}-{v.supplier.branchCode ?? "00000"}
              </dd>
            </div>
          )}
          <div>
            <dt className="inline text-ink-3">{v.method === "check" ? "Check: " : "Paid by: "}</dt>
            <dd className="inline">
              {v.method === "check" ? `No. ${v.checkNumber ?? "—"}${v.checkDate ? `, ${fmt.dateLabel(v.checkDate)}` : ""}` : `${v.methodLabel}${v.bankReference ? `, ref. ${v.bankReference}` : ""}`}
              {v.paidFrom && ` · from ${v.paidFrom.name}`}
            </dd>
          </div>
          {v.method === "bank" && (v.supplier.bankName || v.supplier.bankAccountNumber) && (
            <div>
              <dt className="inline text-ink-3">To: </dt>
              <dd className="inline">{[v.supplier.bankName, v.supplier.bankAccountName, v.supplier.bankAccountNumber].filter(Boolean).join(" · ")}</dd>
            </div>
          )}
        </dl>
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-2 font-semibold">Bill</th>
              <th className="py-2 font-semibold">Their invoice</th>
              <th className="py-2 font-semibold">Bill date</th>
              <th className="py-2 font-semibold">Bill approved</th>
              <th className="w-40 py-2 text-right font-semibold">Amount paid</th>
            </tr>
          </thead>
          <tbody>
            {v.lines.map((l) => (
              <tr key={l.billId} className="border-b border-rule">
                <td className="py-1.5 font-mono">{l.billNo}</td>
                <td className="py-1.5 font-mono">{l.billNumber}</td>
                <td className="py-1.5">{fmt.dateLabel(l.billDate)}</td>
                <td className="py-1.5 text-meta">
                  {l.approvedBy ?? "—"}
                  {l.checkedBy && <span className="block text-ink-3">Tax withheld checked: {l.checkedBy}</span>}
                </td>
                <td className="py-1.5 text-right tabular-nums">
                  {fmt.peso(l.amountCentavos)}
                  {l.partial && <span className="block text-meta text-ink-3">part; {fmt.peso(l.leftAfterCentavos)} left</span>}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-ink font-semibold">
              <td className="py-2" colSpan={4}>
                Total
              </td>
              <td className="py-2 text-right tabular-nums">{fmt.peso(v.totalCentavos)}</td>
            </tr>
          </tfoot>
        </table>
        <p className="mt-2 text-sm">
          <span className="text-ink-3">Amount in words: </span>
          {v.amountInWords}
        </p>
        <SignatureLines
          lines={[
            { step: "prepared", label: "Prepared by" },
            { step: "released", label: "Released by" },
          ]}
          signed={signed.steps}
          timeZone={me.org.timezone}
        />
        <div className="mt-10 grid gap-8 sm:grid-cols-2 print:grid-cols-2">
          <div className="break-inside-avoid">
            <p className="text-meta text-ink-3">Received by (the supplier)</p>
            <div className="h-16" />
            <div className="border-t border-ink pt-1">
              <p className="text-meta text-ink-3">Signature over printed name · Date</p>
            </div>
          </div>
        </div>
      </Sheet>
    </>
  );
}

