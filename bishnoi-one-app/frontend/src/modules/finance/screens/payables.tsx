import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { BillEditor } from "@/src/modules/finance/payables/bill-editor";
import { attachFile, attachSupplierFile, removeFile, removeSupplierFile } from "@/src/modules/finance/payables/actions";
import { BillSteps, DeleteBillDraft, VoidBill } from "@/src/modules/finance/payables/bill-steps";
import { AttachedFiles } from "@/src/modules/finance/payables/files";
import { SupplierImport } from "@/src/modules/finance/payables/import";
import { ImportedDetails } from "../payables/import-details";
import { SupplierForm, SwitchSupplier } from "@/src/modules/finance/payables/supplier-form";
import { VOUCHER_STATUS_LABELS } from "@/src/modules/finance/vouchers/types";
import { BILL_STATE_LABELS, type Bill, type BillChoices, type BillState, type BillSummary, type Supplier, type Withholding } from "@/src/modules/finance/payables/types";

// Payables (app/routers/payables.py): suppliers, and their bills. A bill is made and submitted,
// approved, checked if tax is withheld, and only then posted and ready to pay (Aubrey's flow,
// 2026-10-23); voided rather than changed. Each step is a tick on the Roles screen.

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

function StatusMark({ state }: { state: BillState }) {
  const tone =
    state === "ready" || state === "paid"
      ? "bg-hema-tint text-hema"
      : state === "returned" || state === "partly_paid"
        ? "bg-due-today/15 text-due-today"
        : state === "void"
          ? "bg-danger-tint text-danger"
          : "bg-bench text-ink-2";
  return <span className={`rounded-full px-2 py-0.5 text-meta font-medium ${tone}`}>{BILL_STATE_LABELS[state]}</span>;
}

/** Unpaid / Partly paid / Paid, always beside the amount (you, 2026-10-23: part-payments must be seen). */
function PaymentMark({ bill }: { bill: BillSummary }) {
  if (bill.paymentState === "unpaid") return <span className="block text-meta text-ink-3">Unpaid</span>;
  return <span className={`block text-meta font-semibold ${bill.paymentState === "paid" ? "text-hema" : "text-due-today"}`}>{bill.paymentLabel}</span>;
}

// Each tab is someone's list: drafts and returned (Aubrey), to approve (Malou), to check (Mel),
// ready to pay (Cristal).
const TABS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "draft", label: "Drafts" },
  { key: "returned", label: "Returned" },
  { key: "to_approve", label: "To approve" },
  { key: "to_check", label: "To check" },
  { key: "ready", label: "Ready to pay" },
  { key: "partly_paid", label: "Partly paid" },
  { key: "paid", label: "Paid" },
  { key: "void", label: "Void" },
  { key: "missing", label: "Document missing" },
];

const EVENT_LABELS: Record<string, string> = {
  tax_reviewed: "Bill VAT and withholding reviewed",
  submitted: "Submitted for approval",
  resubmitted: "Corrected and submitted again",
  approved: "Approved",
  returned: "Returned for correction",
  checked: "Tax withheld checked",
  cleared: "Posted to the books: ready to pay",
  voided: "Voided",
};

export async function BillsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const show = one(sp.show);
  const q = one(sp.q);
  const query = new URLSearchParams();
  if (show === "missing") query.set("missing", "true");
  else if (show) query.set("show", show);
  if (q) query.set("q", q);
  for (const key of ["queue", "supplierId", "bucket"]) if (one(sp[key])) query.set(key, one(sp[key]));
  const list = await load<{ items: (BillSummary & { queueNote?: string | null })[]; counts: Record<BillState | "missing", number>; canCreate: boolean; queueLabel: string | null }>(`/finance/bills?${query}`);
  return (
    <>
      <PageHeader
        title="Bills"
        actions={
          list.canCreate && (
            <LinkButton href="/finance/bills/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New bill
            </LinkButton>
          )
        }
      >
        Suppliers&apos; invoices, as the company owes them. A bill is made with its invoice attached and submitted; approved; checked if tax is withheld; and
        only then posted to the books and ready to pay. Returned, it goes back with the reason. A posted bill is voided, never changed.
      </PageHeader>
      {(list.queueLabel || query.has("supplierId") || query.has("bucket")) && <p className="mb-3 text-sm text-ink-2">
        {list.queueLabel ?? "Filtered bills"}{query.has("bucket") ? ` · aging bucket: ${query.get("bucket")}` : ""} · {list.items.length} matching bills · <Link href="/finance/bills" className="text-hema hover:underline">Clear filters</Link> · <Link href="/finance/bills/aging" className="text-hema hover:underline">Accounts payable aging</Link>
      </p>}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Show" className="flex flex-wrap gap-1.5">
          {TABS.map((t) => {
            const n = t.key ? list.counts[t.key as BillState | "missing"] : 0;
            return (
              <Link
                key={t.key}
                href={t.key ? `/finance/bills?show=${t.key}` : "/finance/bills"}
                aria-current={show === t.key ? "page" : undefined}
                className={`rounded-[3px] border px-3 py-1 text-meta ${show === t.key ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:border-control"}`}
              >
                {t.label}
                {n ? <span className={t.key === "missing" || t.key === "returned" ? "font-semibold text-due-today" : "text-ink-3"}> {n}</span> : null}
              </Link>
            );
          })}
        </nav>
        <form className="flex gap-2">
          {["queue", "supplierId", "bucket"].map((key) => query.has(key) ? <input suppressHydrationWarning key={key} type="hidden" name={key} value={query.get(key)!} /> : null)}
          {show && <input suppressHydrationWarning type="hidden" name="show" value={show} />}
          <input suppressHydrationWarning name="q" defaultValue={q} placeholder="Supplier, invoice, PO or reference" aria-label="Find a bill" className="h-8 w-64 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </form>
      </div>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty title={q || show ? "No matching bills" : "No bills yet"} icon="lists">
            {!q && !show && list.canCreate ? "Enter the first one with New bill." : null}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[50rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="py-2 pr-3 pl-5 font-semibold">Bill</th>
                  <th className="px-3 py-2 font-semibold">Supplier</th>
                  <th className="px-3 py-2 font-semibold">Their invoice</th>
                  <th className="px-3 py-2 font-semibold">Date</th>
                  <th className="px-3 py-2 font-semibold">Due</th>
                  <th className="px-3 py-2 text-right font-semibold">To pay</th>
                  <th className="px-3 py-2 text-right font-semibold">Left to pay</th>
                  <th className="py-2 pr-5 pl-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {list.items.map((b) => (
                  <tr key={b.id} className="relative hover:bg-bench/40">
                    <td className="py-2.5 pr-3 pl-5 font-mono text-meta">
                      <Link href={`/finance/bills/${b.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {b.no}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5">
                      {b.supplier.name}
                      {b.documentMissing && b.status !== "void" && <span className="block text-meta text-due-today">Document missing</span>}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-meta">{b.billNumber}</td>
                    <td className="px-3 py-2.5 text-ink-2">{fmt.dateLabel(b.billDate)}</td>
                    <td className="px-3 py-2.5 text-ink-2">{b.status === "void" ? "" : fmt.dateLabel(b.dueDate)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{fmt.peso(b.payableCentavos)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{b.status === "recorded" ? fmt.peso(b.leftCentavos) : ""}</td>
                    <td className="py-2.5 pr-5 pl-3">
                      <StatusMark state={b.state} />
                      {b.queueNote && <span className="mt-1 block text-meta text-ink-2">{b.queueNote}</span>}
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

export async function NewBillPage() {
  const me = await getCompanyMe();
  const choices = await load<BillChoices>("/finance/bills/choices");
  return (
    <>
      <PageHeader title="New bill" crumbs={[{ href: "/finance/bills", label: "Bills" }]}>
        Saved as a draft first: attach the supplier&apos;s invoice, check it against the PO and delivery receipt, then submit it for approval from the bill&apos;s
        page.
      </PageHeader>
      <BillEditor bill={null} choices={choices} org={me.org} />
    </>
  );
}

const WAITING: Partial<Record<BillState, string>> = {
  draft: "A draft: whoever made it submits it for approval.",
  returned: "Back with whoever submitted it, to be corrected and submitted again.",
  to_approve: "Waiting for approval by someone whose role may approve bills.",
  to_check: "Approved. Waiting for the tax withheld to be checked by someone whose role may check it.",
};

/** The bill's road to being paid, with who did each step so far: always in view, not behind a click. */
function ApprovalPath({ bill: b }: { bill: Bill }) {
  const at = b.state === "to_approve" ? 1 : b.state === "to_check" ? 2 : 0;
  const submitter = at >= 1 ? ([...b.events].reverse().find((e) => e.kind === "submitted" || e.kind === "resubmitted")?.who ?? null) : null;
  const steps = [
    { label: "Submitted", who: submitter },
    { label: "Approved", who: b.approvedBy },
    ...(b.needsCheck ? [{ label: "Tax withheld checked", who: b.checkedBy }] : []),
    { label: "Posted, ready to pay", who: null },
  ];
  return (
    <ol className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-meta">
      {steps.map((x, i) => (
        <li key={x.label} className="flex items-center gap-2">
          {i > 0 && (
            <span className="text-ink-3" aria-hidden>
              →
            </span>
          )}
          <span className={x.who ? "font-semibold text-hema" : i === at ? "font-semibold text-ink" : "text-ink-3"}>
            {x.label}
            {x.who && <span className="font-normal text-ink-2"> · {x.who}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

export async function BillPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const editing = one((await searchParams).edit) === "1";
  const b = await load<Bill>(`/finance/bills/${enc(id)}`);
  const crumbs = [{ href: "/finance/bills", label: "Bills" }];
  const title = `Bill ${b.no} · ${b.supplier.name}`;
  const when = fmt.on({ dateStyle: "medium", timeStyle: "short" });
  const lastReturn = [...b.events].reverse().find((e) => e.kind === "returned");

  if (editing && b.canEdit) {
    const choices = await load<BillChoices>("/finance/bills/choices");
    return (
      <>
        <PageHeader title={title} crumbs={crumbs} />
        <BillEditor bill={b} choices={choices} org={me.org} />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={title}
        crumbs={crumbs}
        actions={
          <>
            {b.canEdit && (
              <>
                <LinkButton href={`/finance/bills/${b.id}?edit=1`}>Edit</LinkButton>
                <DeleteBillDraft id={b.id} />
              </>
            )}
            {b.canPay && b.leftCentavos - b.setAsideCentavos > 0 && (
              <LinkButton href={`/finance/vouchers/new?supplier=${b.supplier.id}&bill=${b.id}`} variant="primary">
                Pay this bill
              </LinkButton>
            )}
            {b.canVoid && <VoidBill id={b.id} label={`Bill ${b.no}`} />}
          </>
        }
      >
        <StatusMark state={b.state} />
        {b.status === "void" && (
          <span className="ml-2 text-meta text-danger">
            Voided by {b.voidedBy}: {b.voidReason}
          </span>
        )}
      </PageHeader>

      {b.status === "recorded" && (
        <Sheet className="mb-5 px-5 py-4">
          <p className="text-sm">
            <span className="font-semibold">{fmt.peso(b.paidCentavos)} paid</span> of {fmt.peso(b.payableCentavos)} ·{" "}
            <span className={b.leftCentavos ? "font-semibold" : ""}>{fmt.peso(b.leftCentavos)} left to pay</span> <PaymentMark bill={b} />
            {b.setAsideCentavos > 0 && <span className="text-due-today"> · {fmt.peso(b.setAsideCentavos)} in a voucher not released yet</span>}
          </p>
          {b.vouchers.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-meta text-ink-2">
              {b.vouchers.map((x) => (
                <li key={x.id}>
                  <Link href={`/finance/vouchers/${x.id}`} className="font-mono font-semibold text-hema hover:underline">
                    {x.number}
                  </Link>{" "}
                  · {fmt.peso(x.amountCentavos)} · {VOUCHER_STATUS_LABELS[x.status as keyof typeof VOUCHER_STATUS_LABELS] ?? x.status}
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      )}

      {b.state === "returned" && lastReturn && (
        <p className="mb-4 rounded-[3px] bg-due-today/10 px-4 py-2 text-sm">
          <span className="font-semibold">Returned for correction</span> by {lastReturn.who}: {lastReturn.text}
        </p>
      )}

      {b.status === "draft" && (
        <Sheet className="mb-5 px-5 py-4">
          <SectionTitle icon="approvals">Approval</SectionTitle>
          {b.status === "draft" && !b.taxReviewed && <p className="mb-3 text-sm">Before submission, <Link href={`/finance/bills/${b.id}?edit=1`} className="text-hema underline">edit this draft</Link> and confirm its VAT and withholding choices.</p>}
          {!b.supplier.tin && <p className="mb-3 text-meta text-ink-2">Supplier TIN is missing or unresolved. This record does not establish complete BIR supplier details.</p>}
          <ApprovalPath bill={b} />
          {b.problem ? (
            <p className="text-sm text-danger">{b.problem}</p>
          ) : b.canSubmit || b.canApprove || b.canCheck || b.canReturn ? (
            <BillSteps bill={b} />
          ) : (
            <p className="text-sm text-ink-2">{WAITING[b.state] ?? "Waiting for the next step."}</p>
          )}
        </Sheet>
      )}

      <Sheet className="px-6 py-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Particulars
            items={[
              ["Supplier", <Link key="s" href={`/finance/suppliers/${b.supplier.id}`} className="text-hema hover:underline">{b.supplier.name}</Link>],
              ["TIN", b.supplier.tin ? `${b.supplier.tin}-${b.supplier.branchCode ?? "00000"}` : null],
              ["Their invoice", <span key="n" className="font-mono">{b.billNumber}</span>],
              ["PO number", b.poNumber],
              ["Delivery receipt", b.drNumber],
            ]}
          />
          <Particulars
            items={[
              ["Bill date", fmt.dateLabel(b.billDate)],
              ["Due date", fmt.dateLabel(b.dueDate)],
              ["Checked against", [b.checkedPo && "PO", b.checkedDr && "delivery receipt"].filter(Boolean).join(" and ") || <span key="c" className="text-due-today">Not marked</span>],
              ["Zoho", b.zohoRef],
              ["Oojeema", b.oojeemaRef],
              ["Approved by", b.approvedBy],
              ["Tax withheld checked by", b.checkedBy],
            ]}
          />
        </div>
        <table className="mt-5 w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-1.5 pr-2 font-semibold">Account</th>
              <th className="px-2 py-1.5 font-semibold">Description</th>
              <th className="px-2 py-1.5 font-semibold">Purchase type</th>
              <th className="w-28 px-2 py-1.5 font-semibold">VAT</th>
              <th className="w-28 px-2 py-1.5 font-semibold">Withheld</th>
              <th className="w-32 py-1.5 pl-2 text-right font-semibold">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {b.lines.map((l, i) => (
              <tr key={i}>
                <td className="py-1.5 pr-2">{l.account ? `${l.account.code} · ${l.account.name}` : "—"}</td>
                <td className="px-2 py-1.5 text-ink-2">{l.description}</td>
                <td className="px-2 py-1.5 text-ink-2">{l.purchaseTypeLabel}</td>
                <td className="px-2 py-1.5 text-meta text-ink-2">{l.vatLabel}</td>
                <td className="px-2 py-1.5 text-meta text-ink-2">{l.withholding ? `${l.withholding} · ${(l.withholdingRateBp ?? 0) / 100}%` : "None"}</td>
                <td className="py-1.5 pl-2 text-right tabular-nums">{fmt.peso(l.amountCentavos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-meta text-ink-3">{b.amountsIncludeVat ? "Amounts include VAT, as on the supplier's invoice." : "Amounts are before VAT."}</p>
        <div className="mt-4 ml-auto max-w-sm space-y-1 text-sm">
          {(
            [
              ["Before VAT", b.netCentavos],
              ["VAT (input)", b.vatCentavos],
              ["Total", b.totalCentavos],
            ] as const
          ).map(([label, value]) => (
            <p key={label} className="flex justify-between gap-6">
              <span className="text-ink-2">{label}</span>
              <span className="tabular-nums">{fmt.peso(value)}</span>
            </p>
          ))}
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">Tax withheld (EWT)</span>
            <span className="tabular-nums">({fmt.peso(b.withheldCentavos)})</span>
          </p>
          <p className="flex justify-between gap-6 border-t border-ink pt-1 font-semibold">
            <span>To pay the supplier</span>
            <span className="tabular-nums">{fmt.peso(b.payableCentavos)}</span>
          </p>
        </div>
        {b.notes && <p className="mt-4 text-meta text-ink-2">{b.notes}</p>}
      </Sheet>

      <Sheet className="mt-5 px-5 py-4">
        <SectionTitle>The supplier&apos;s invoice</SectionTitle>
        <AttachedFiles
          files={b.files}
          openBase={`/finance/bills/${b.id}/files`}
          label="Attach the supplier's invoice"
          attach={b.canAttach ? attachFile.bind(null, b.id) : undefined}
          remove={b.canAttach ? removeFile.bind(null, b.id) : undefined}
          empty={<p className="text-sm text-due-today">Document missing: the supplier&apos;s invoice isn&apos;t attached yet.</p>}
        />
      </Sheet>

      {b.events.length > 0 && (
        <Sheet className="mt-5 px-5 py-4">
          <SectionTitle>History</SectionTitle>
          <ul className="divide-y divide-rule text-sm">
            {b.events.map((e, i) => (
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
      )}

      <p className="mt-3 text-meta text-ink-3">
        Entered by {b.createdBy}.{b.recordedBy && ` Posted by ${b.recordedBy}.`}{" "}
        {b.entryId && (
          <Link href="/finance/ledger?source=bill" className="text-hema hover:underline">
            View journal entry
          </Link>
        )}
      </p>
    </>
  );
}

// --- suppliers -----------------------------------------------------------------------------------

type Account = { id: string; code: string; name: string };
type SupplierList = { items: Supplier[]; withholding: Withholding[]; payablesAccounts: Account[]; canAdd: boolean; canEdit: boolean; canDeactivate: boolean };
type SupplierDetail = Supplier & { bills: BillSummary[]; withholdingChoices: Withholding[]; payablesAccounts: Account[]; canAdd: boolean; canEdit: boolean; canDeactivate: boolean };

const personName = (c: { salutation: string | null; firstName: string | null; lastName: string | null }) =>
  [c.salutation, c.firstName, c.lastName].filter(Boolean).join(" ") || null;

/** The suppliers, as Zoho's All Vendors lists them: name, company, email, phone, and what's owed each. */
export async function SuppliersPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const q = one((await searchParams).q);
  const list = await load<SupplierList>(`/finance/suppliers${q ? `?q=${enc(q)}` : ""}`);
  return (
    <>
      <PageHeader
        title="Suppliers"
        actions={
          list.canAdd && (
            <LinkButton href="/finance/suppliers/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add supplier
            </LinkButton>
          )
        }
      >
        Who the company buys from, with what each bill from them needs: their TIN, whether they charge VAT, and the tax usually withheld from them.
        Payables is what&apos;s owed each on recorded bills.
      </PageHeader>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">{list.canAdd && <SupplierImport />}</div>
        <form>
          <input suppressHydrationWarning name="q" defaultValue={q} placeholder="Name, company or TIN" aria-label="Find a supplier" className="h-8 w-64 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </form>
      </div>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty title={q ? "No matching suppliers" : "No suppliers yet"} icon="people">
            {!q && list.canAdd ? "Add the first one with Add supplier." : null}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="py-2 pr-3 pl-5 font-semibold">Name</th>
                  <th className="px-3 py-2 font-semibold">Company name</th>
                  <th className="px-3 py-2 font-semibold">Email</th>
                  <th className="px-3 py-2 font-semibold">Phone</th>
                  <th className="py-2 pr-5 pl-3 text-right font-semibold">Payables</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {list.items.map((s) => (
                  <tr key={s.id} className={`relative hover:bg-bench/40 ${s.isActive ? "" : "text-ink-3"}`}>
                    <td className="py-2.5 pr-3 pl-5">
                      <Link href={`/finance/suppliers/${s.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {s.name}
                      </Link>
                      {!s.isActive && <span className="ml-2 text-meta">switched off</span>}
                      <span className="block text-meta text-ink-3">
                        {s.tin ? `TIN ${s.tin}-${s.branchCode ?? "00000"}` : "No TIN"}
                        {s.withholding ? ` · ${s.withholding.code} ${s.withholding.rateBp / 100}%` : ""}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-ink-2">{s.companyName}</td>
                    <td className="px-3 py-2.5 text-ink-2">{s.email}</td>
                    <td className="px-3 py-2.5 text-ink-2">{s.phone ?? s.mobile}</td>
                    <td className="py-2.5 pr-5 pl-3 text-right tabular-nums">{fmt.peso(s.owedCentavos)}</td>
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

export async function NewSupplierPage() {
  // The supplier list carries the withholding codes and payables accounts the form offers.
  const list = await load<SupplierList>("/finance/suppliers");
  return (
    <>
      <PageHeader title="Add supplier" crumbs={[{ href: "/finance/suppliers", label: "Suppliers" }]} />
      <Sheet className="max-w-[56rem] px-5 py-6 sm:px-8">
        <SupplierForm supplier={null} withholding={list.withholding} accounts={list.payablesAccounts} />
      </Sheet>
    </>
  );
}

export async function SupplierPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const editing = one((await searchParams).edit) === "1";
  const s = await load<SupplierDetail>(`/finance/suppliers/${enc(id)}`);
  const crumbs = [{ href: "/finance/suppliers", label: "Suppliers" }];
  if (editing && s.canEdit) {
    return (
      <>
        <PageHeader title={s.name} crumbs={crumbs} />
        <Sheet className="max-w-[56rem] px-5 py-6 sm:px-8">
          <SupplierForm supplier={s} withholding={s.withholdingChoices} accounts={s.payablesAccounts} />
        </Sheet>
      </>
    );
  }
  return (
    <>
      <PageHeader
        title={s.name}
        crumbs={crumbs}
        actions={
          <>
            {s.canEdit && <LinkButton href={`/finance/suppliers/${s.id}?edit=1`}>Edit</LinkButton>}
            {s.canDeactivate && <SwitchSupplier id={s.id} isActive={s.isActive} />}
            {may(me, "bills.create") && s.isActive && (
              <LinkButton href="/finance/bills/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                New bill
              </LinkButton>
            )}
          </>
        }
      >
        {s.companyName && s.companyName !== s.name && <span className="text-ink-2">{s.companyName}</span>}
        {!s.isActive && <span className="ml-2 text-meta text-ink-3">Switched off: not offered on new bills.</span>}
      </PageHeader>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Sheet className="px-4 py-3">
          <p className="text-meta text-ink-3">Payables</p>
          <p className="text-heading tabular-nums">{fmt.peso(s.owedCentavos)}</p>
          <p className="text-meta text-ink-3">On recorded bills</p>
        </Sheet>
      </div>
      <Sheet className="px-6 py-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Particulars
            items={[
              ["Primary contact", personName(s)],
              ["Email", s.email],
              ["Work phone", s.phone],
              ["Mobile", s.mobile],
              ["Address", s.address],
              ["Remarks", s.notes],
            ]}
          />
          <Particulars
            items={[
              ["TIN", s.tin ? `${s.tin}-${s.branchCode ?? "00000"}` : null],
              ["VAT", !s.taxDefaultsConfirmed ? "Tax defaults not confirmed" : s.vatRegistered ? "VAT-registered" : "Not VAT-registered"],
              ["Usually withheld", !s.taxDefaultsConfirmed ? "Not confirmed" : s.withholding ? `${s.withholding.code} · ${s.withholding.name} · ${s.withholding.rateBp / 100}%` : "Nothing"],
              ["Terms", s.termsDays ? `${s.termsDays} days` : "Cash"],
              ["Accounts payable", s.payablesAccount ? `${s.payablesAccount.code} · ${s.payablesAccount.name}` : "The default"],
              ["Bank", [s.bankName, s.bankAccountName, s.bankAccountNumber].filter(Boolean).join(" · ") || null],
              ["Added by", s.createdBy],
            ]}
          />
        </div>
      </Sheet>
      <ImportedDetails details={s.importDetails} />
      {s.contacts.length > 0 && (
        <Sheet className="mt-5 px-5 py-4">
          <SectionTitle>Contact persons</SectionTitle>
          <ul className="divide-y divide-rule">
            {s.contacts.map((c, i) => (
              <li key={i} className="flex flex-wrap gap-x-6 gap-y-1 py-2 text-sm">
                <span className="min-w-40 font-semibold">{personName(c) ?? "—"}</span>
                {c.designation && <span className="text-ink-2">{c.designation}</span>}
                {c.email && <span className="text-ink-2">{c.email}</span>}
                {(c.phone || c.mobile) && <span className="text-ink-2">{[c.phone, c.mobile].filter(Boolean).join(" · ")}</span>}
              </li>
            ))}
          </ul>
        </Sheet>
      )}
      <Sheet className="mt-5 px-5 py-4">
        <SectionTitle>Documents</SectionTitle>
        <AttachedFiles
          files={s.files}
          openBase={`/finance/suppliers/${s.id}/files`}
          label="Attach the supplier's papers"
          attach={s.canEdit ? attachSupplierFile.bind(null, s.id) : undefined}
          remove={s.canEdit ? removeSupplierFile.bind(null, s.id) : undefined}
          empty={<p className="text-sm text-ink-3">None yet: their BIR 2303, accreditation or contract can be kept here.</p>}
        />
      </Sheet>
      <Sheet className="mt-5">
        <div className="px-5 pt-4">
          <SectionTitle>Bills</SectionTitle>
        </div>
        {s.bills.length === 0 ? (
          <p className="px-5 pb-4 text-sm text-ink-3">No bills from them yet.</p>
        ) : (
          <ul className="divide-y divide-rule border-t border-rule">
            {s.bills.map((b) => (
              <li key={b.id} className="relative flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-2.5 text-sm hover:bg-bench/40">
                <Link href={`/finance/bills/${b.id}`} className="w-24 font-mono text-meta font-semibold text-hema after:absolute after:inset-0 hover:underline">
                  {b.no}
                </Link>
                <span className="min-w-0 flex-1 font-mono text-meta">{b.billNumber}</span>
                <span className="text-ink-2">{fmt.dateLabel(b.billDate)}</span>
                <span className="w-32 text-right tabular-nums">{fmt.peso(b.payableCentavos)}</span>
                <span className="w-36 text-right text-meta tabular-nums">{b.status === "recorded" && `${fmt.peso(b.leftCentavos)} left`}</span>
                <StatusMark state={b.state} />
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
