import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { InvoiceEditor } from "../invoices/editor";
import { AddSeries, SwitchSeries } from "../invoices/series-editor";
import { DeleteDraft, IssueInvoice, PrintButton, RecordPayment, RemovePayment, VoidInvoice } from "../invoices/steps";
import { STATUS_LABELS, type Ageing, type Invoice, type InvoiceStatus, type InvoiceSummary, type Series, type TaxChoices } from "../invoices/types";
import { Amount } from "@/src/platform/ui/amount";

// Sales invoices (app/routers/invoices.py): drafts, issued with the next
// number of the BIR's series, and voided rather than changed once issued.

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

type SeriesList = { items: Series[]; canSetup: boolean; crmLinked: boolean };
type TaxSetup = { pack: { categories: TaxChoices["categories"]; treatments: TaxChoices["treatments"] }; profile: { pricesIncludeTax: boolean }; today: string };

async function taxChoices(): Promise<{ choices: TaxChoices; today: string }> {
  const setup = await load<TaxSetup>("/tax/setup");
  return { choices: { categories: setup.pack.categories, treatments: setup.pack.treatments, pricesIncludeTax: setup.profile.pricesIncludeTax }, today: setup.today };
}

const TABS: { key: "" | InvoiceStatus; label: string }[] = [
  { key: "", label: "All" },
  { key: "draft", label: "Drafts" },
  { key: "issued", label: "Issued" },
  { key: "void", label: "Void" },
];

function StatusMark({ status }: { status: InvoiceStatus }) {
  const tone = status === "issued" ? "bg-hema-tint text-hema" : status === "void" ? "bg-danger-tint text-danger" : "bg-bench text-ink-2";
  return <span className={`rounded-full px-2 py-0.5 text-meta font-medium ${tone}`}>{STATUS_LABELS[status]}</span>;
}

export async function InvoicesPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const status = one(sp.status);
  const q = one(sp.q);
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (q) query.set("q", q);
  const list = await load<{ items: InvoiceSummary[]; counts: Record<InvoiceStatus, number> }>(`/finance/invoices?${query}`);
  return (
    <>
      <PageHeader
        title="Sales invoices"
        actions={
          may(me, "invoices.create") && (
            <LinkButton href="/invoices/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New invoice
            </LinkButton>
          )
        }
      >
        Invoices to customers, with their VAT worked out. A draft takes its number when it&apos;s issued, from the BIR&apos;s series, and is posted to the
        books; an issued invoice is voided, never changed.
      </PageHeader>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="Show" className="flex flex-wrap gap-1.5">
          {TABS.map((t) => (
            <Link
              key={t.key}
              href={t.key ? `/invoices?status=${t.key}` : "/invoices"}
              aria-current={status === t.key ? "page" : undefined}
              className={`rounded-[3px] border px-3 py-1 text-meta ${status === t.key ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:border-control"}`}
            >
              {t.label}
              {t.key && list.counts[t.key] ? <span className="text-ink-3"> {list.counts[t.key]}</span> : null}
            </Link>
          ))}
        </nav>
        <form className="flex gap-2">
          {status && <input type="hidden" name="status" value={status} />}
          <input name="q" defaultValue={q} placeholder="Customer, number or reference" aria-label="Find an invoice" className="h-8 w-64 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </form>
      </div>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty title={q || status ? "No matching invoices" : "No invoices yet"} icon="lists">
            {!q && !status && may(me, "invoices.create") ? "Make the first one with New invoice." : null}
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="py-2 pr-3 pl-5 font-semibold">Number</th>
                  <th className="px-3 py-2 font-semibold">Customer</th>
                  <th className="px-3 py-2 font-semibold">Date</th>
                  <th className="px-3 py-2 font-semibold">Due date</th>
                  <th className="px-3 py-2 text-right font-semibold">Total</th>
                  <th className="py-2 pr-5 pl-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {list.items.map((i) => (
                  <tr key={i.id} className="relative hover:bg-bench/40">
                    <td className="py-2.5 pr-3 pl-5 font-mono text-meta">
                      <Link href={`/invoices/${i.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {i.number ?? "Draft"}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5">
                      {i.customer.name}
                      {i.reference && <span className="text-ink-3"> · Ref. {i.reference}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-ink-2">{fmt.dateLabel(i.date)}</td>
                    <td className="px-3 py-2.5 text-ink-2">{i.status === "issued" ? fmt.dateLabel(i.dueDate) : ""}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{i.status === "draft" ? "" : fmt.peso(i.totalCentavos)}</td>
                    <td className="py-2.5 pr-5 pl-3">
                      <StatusMark status={i.status} />
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

export async function NewInvoicePage() {
  const me = await getCompanyMe();
  const [{ choices, today }, series] = await Promise.all([taxChoices(), load<SeriesList>("/finance/invoices/series")]);
  return (
    <>
      <PageHeader title="New invoice" crumbs={[{ href: "/invoices", label: "Sales invoices" }]}>
        Saved as a draft first: its amounts and VAT are worked out, then it&apos;s issued from the invoice&apos;s page.
      </PageHeader>
      <InvoiceEditor invoice={null} choices={choices} org={me.org} today={today} crmLinked={series.crmLinked} />
    </>
  );
}

export async function InvoicePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const editing = one((await searchParams).edit) === "1";
  const inv = await load<Invoice>(`/finance/invoices/${enc(id)}`);
  const crumbs = [{ href: "/invoices", label: "Sales invoices" }];

  if (inv.status === "draft" && editing && may(me, "invoices.create")) {
    const [{ choices, today }, series] = await Promise.all([taxChoices(), load<SeriesList>("/finance/invoices/series")]);
    return (
      <>
        <PageHeader title={`Draft for ${inv.customer.name}`} crumbs={crumbs} />
        <InvoiceEditor invoice={inv} choices={choices} org={me.org} today={today} crmLinked={series.crmLinked} />
      </>
    );
  }

  const c = inv.computed;
  const series = inv.status === "draft" && may(me, "invoices.issue") ? (await load<SeriesList>("/finance/invoices/series")).items : [];
  return (
    <>
      <div className="print:hidden">
        <PageHeader
          title={inv.number ? `Invoice ${inv.number}` : `Draft for ${inv.customer.name}`}
          crumbs={crumbs}
          actions={
            <>
              {inv.status === "draft" && may(me, "invoices.create") && (
                <>
                  <LinkButton href={`/invoices/${inv.id}?edit=1`}>Edit</LinkButton>
                  <DeleteDraft id={inv.id} />
                </>
              )}
              {inv.status !== "draft" && <PrintButton />}
              {inv.status === "issued" && may(me, "invoices.void") && inv.number && <VoidInvoice id={inv.id} number={inv.number} />}
            </>
          }
        >
          <StatusMark status={inv.status} />
          {inv.status === "void" && (
            <span className="ml-2 text-meta text-danger">
              Voided by {inv.voidedBy}: {inv.voidReason}
            </span>
          )}
        </PageHeader>
        {inv.status === "draft" && (
          <Sheet className="mb-5 px-5 py-4">
            <SectionTitle icon="approvals">Issue</SectionTitle>
            {inv.problem ? (
              <p className="text-sm text-danger">{inv.problem} Edit the draft to fix it.</p>
            ) : c?.warnings.length ? (
              <p className="text-sm text-danger">{c.warnings.join(" ")} Fill them in under Tax before issuing.</p>
            ) : may(me, "invoices.issue") ? (
              <IssueInvoice id={inv.id} series={series} />
            ) : (
              <p className="text-sm text-ink-2">Only users with permission to issue invoices can issue this draft.</p>
            )}
          </Sheet>
        )}
      </div>

      {/* The invoice itself, as it prints. */}
      <Sheet className={`px-8 py-7 print:border-0 print:shadow-none ${inv.status === "void" ? "opacity-70" : ""}`}>
        <div className="flex flex-wrap justify-between gap-6 border-b-[3px] border-double border-ink pb-4">
          <div>
            <p className="text-heading">{c?.seller.registeredName ?? me.org.name}</p>
            {c?.seller.tradeName && <p className="text-meta text-ink-2">{c.seller.tradeName}</p>}
            {c?.seller.address && <p className="text-meta text-ink-2">{c.seller.address}</p>}
            {c?.seller.tin && <p className="text-meta text-ink-2">{c.seller.regimeName} TIN {c.seller.tin}</p>}
          </div>
          <div className="text-right">
            <p className="text-stamp text-ink-3 uppercase">{c?.document ?? "Sales Invoice"}</p>
            <p className="font-mono text-heading">{inv.number ?? "DRAFT"}</p>
            {inv.status === "void" && <p className="text-stamp text-danger uppercase">Void</p>}
          </div>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Particulars
            items={[
              ["Sold to", inv.customer.name],
              ["TIN", inv.customer.tin],
              ["Address", inv.customer.address],
              ["Salesperson", inv.salesperson?.name ?? null],
              ...(inv.buyerIdNumber ? ([[c?.treatment.name ?? "ID number", inv.buyerIdNumber]] as [string, string][]) : []),
            ]}
          />
          <Particulars
            items={[
              ["Date", fmt.dateLabel(inv.date)],
              ["Terms", inv.termsDays ? `${inv.termsDays} days` : "Cash on delivery"],
              ["Due date", fmt.dateLabel(inv.dueDate)],
              ["Reference", inv.reference],
            ]}
          />
        </div>
        {c ? (
          <>
            <table className="mt-5 w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="py-1.5 pr-2 font-semibold">Item</th>
                  <th className="w-16 px-2 py-1.5 text-right font-semibold">Qty</th>
                  <th className="w-32 px-2 py-1.5 text-right font-semibold">Unit price</th>
                  <th className="w-24 px-2 py-1.5 font-semibold">VAT</th>
                  <th className="w-32 py-1.5 pl-2 text-right font-semibold">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {c.lines.map((l, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-2">{l.description ?? inv.lines[i]?.description ?? ""}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{inv.lines[i]?.quantity}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{fmt.peso(inv.lines[i]?.unitPriceCentavos ?? 0)}</td>
                    <td className="px-2 py-1.5 text-meta text-ink-2">{l.codeName}</td>
                    <td className="py-1.5 pl-2 text-right tabular-nums">{fmt.peso(l.totalCentavos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-4 ml-auto max-w-sm space-y-1 text-sm">
              {c.summary.map((s) => (
                <p key={s.key} className="flex justify-between gap-6">
                  <span className="text-ink-2">{s.label}</span>
                  <span className="tabular-nums">{fmt.peso(s.amountCentavos)}</span>
                </p>
              ))}
              {c.relief && (
                <p className="flex justify-between gap-6">
                  <span className="text-ink-2">{c.relief.label}</span>
                  <span className="tabular-nums">({fmt.peso(c.relief.amountCentavos)})</span>
                </p>
              )}
              <p className="flex justify-between gap-6 border-t border-ink pt-1 font-semibold">
                <span>Total amount due</span>
                <span className="tabular-nums">{fmt.peso(c.totalDueCentavos)}</span>
              </p>
            </div>
            {c.notice && <p className="mt-4 text-center text-meta font-semibold">{c.notice}</p>}
          </>
        ) : (
          <p className="mt-5 text-sm text-ink-3">The amounts appear once the lines are fixed.</p>
        )}
        {inv.notes && <p className="mt-4 text-meta text-ink-2">{inv.notes}</p>}
        {inv.series && (
          <p className="mt-6 border-t border-rule pt-2 text-meta text-ink-3">
            ATP No. {inv.series.atpNumber}, issued {fmt.dateLabel(inv.series.atpDate)}. Approved series {inv.series.range}.
          </p>
        )}
      </Sheet>
      {inv.status === "issued" && (
        <Sheet className="mt-5 px-5 py-4 print:hidden">
          <SectionTitle icon="payments">
            Payments{" "}
            <span className="font-normal text-ink-3">
              · {fmt.peso(inv.paidCentavos)} received, {fmt.peso(inv.balanceCentavos)} outstanding
            </span>
          </SectionTitle>
          {inv.payments.length > 0 && (
            <ul className="mb-3 divide-y divide-rule">
              {inv.payments.map((p) => (
                <li key={p.id} className={`flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-sm ${p.removedAt ? "text-ink-3 line-through" : ""}`}>
                  <span className="w-28">{fmt.dateLabel(p.paidOn)}</span>
                  <span className="w-32 tabular-nums">{fmt.peso(p.amountCentavos)}</span>
                  <span className="min-w-0 flex-1">
                    {p.methodLabel}
                    {p.reference && <span className="text-ink-3"> · {p.reference}</span>}
                    <span className="text-ink-3"> · {p.recordedBy}</span>
                  </span>
                  {p.removedAt ? (
                    <span className="text-meta no-underline">Reversed by {p.removedBy}</span>
                  ) : (
                    may(me, "invoices.void") && <RemovePayment id={inv.id} paymentId={p.id} />
                  )}
                </li>
              ))}
            </ul>
          )}
          {inv.balanceCentavos > 0 ? (
            may(me, "invoices.collect") && <RecordPayment id={inv.id} owed={inv.balanceCentavos} methods={inv.methods} org={me.org} today={fmt.todayKey()} />
          ) : (
            <p className="text-sm text-ink-2">Paid in full.</p>
          )}
        </Sheet>
      )}
      {inv.status !== "draft" && (
        <p className="mt-3 text-meta text-ink-3 print:hidden">
          Issued by {inv.issuedBy}.{" "}
          {inv.entryId && (
            <Link href="/ledger?source=invoice" className="text-hema hover:underline">
              View journal entry
            </Link>
          )}
        </p>
      )}
    </>
  );
}

export async function SeriesPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [series, { today }] = await Promise.all([load<SeriesList>("/finance/invoices/series"), taxChoices()]);
  return (
    <>
      <PageHeader title="Invoice numbers" crumbs={[{ href: "/invoices", label: "Sales invoices" }]}>
        Each series is a run of numbers the BIR authorized, from its Authority to Print. Invoices take them in order and never go past the last; when a
        series runs low, apply for the next and add it here.
      </PageHeader>
      {series.canSetup && (
        <div className="mb-4">
          <AddSeries today={today} />
        </div>
      )}
      <Sheet>
        {series.items.length === 0 ? (
          <Empty title="No invoice numbers yet" icon="lists">
            {series.canSetup ? "Add the series from the BIR's Authority to Print before issuing invoices." : "An administrator adds them from the BIR's Authority to Print."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {series.items.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">
                    {s.name} {!s.isActive && <span className="font-normal text-ink-3">· inactive</span>}
                  </p>
                  <p className="text-meta text-ink-2">
                    ATP No. {s.atpNumber}, issued {fmt.dateLabel(s.atpDate)} · {s.firstNumber} to {s.lastNumber}
                  </p>
                </div>
                <p className={`text-meta ${s.left === 0 ? "text-danger" : s.left < 50 ? "text-danger" : "text-ink-2"}`}>
                  {s.left === 0 ? "Fully used" : `${fmt.count(s.left)} left · next ${s.nextNumber}`}
                </p>
                {series.canSetup && s.left > 0 && <SwitchSeries id={s.id} isActive={s.isActive} />}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

// --- receivables ---------------------------------------------------------------------------------

/** One colour per bucket, from calm to urgent; always beside the words that say it. */
const BUCKET_TONES: Record<string, string> = {
  current: "bg-due-later",
  d1_30: "bg-due-today",
  d31_60: "bg-danger/60",
  d61_90: "bg-danger/80",
  over_90: "bg-danger",
};

export async function ReceivablesPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const age = await load<Ageing>("/finance/receivables");
  const late = age.totalCentavos - (age.buckets.find((b) => b.key === "current")?.amountCentavos ?? 0);
  return (
    <>
      <PageHeader title="Receivables" crumbs={[{ href: "/invoices", label: "Sales invoices" }]}>
        What customers owe on issued invoices, and how late it is, as of {fmt.dateLabel(age.on)}. The latest are listed first.
      </PageHeader>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Sheet className="px-4 py-3 lg:col-span-1">
          <p className="text-meta text-ink-3">Total outstanding</p>
          <p className="text-figure tabular-nums"><Amount text={fmt.peso(age.totalCentavos)} /></p>
          <p className={`text-meta ${late ? "text-danger" : "text-ink-3"}`}>{late ? `${fmt.peso(late)} past due` : "Nothing past due"}</p>
        </Sheet>
        {age.buckets.map((b) => (
          <Sheet key={b.key} className="px-4 py-3">
            <p className="flex items-center gap-1.5 text-meta text-ink-3">
              <span className={`inline-block size-2 rounded-full ${BUCKET_TONES[b.key]}`} aria-hidden />
              {b.label}
            </p>
            <p className="text-heading tabular-nums">{fmt.peso(b.amountCentavos)}</p>
          </Sheet>
        ))}
      </div>
      {age.totalCentavos > 0 && (
        <div className="mb-5 flex h-3 overflow-hidden rounded-full bg-bench" role="img" aria-label={age.buckets.map((b) => `${b.label}: ${fmt.peso(b.amountCentavos)}`).join(", ")}>
          {age.buckets.map((b) => (b.amountCentavos ? <span key={b.key} className={BUCKET_TONES[b.key]} style={{ width: `${(b.amountCentavos / age.totalCentavos) * 100}%` }} /> : null))}
        </div>
      )}
      <Sheet>
        {age.customers.length === 0 ? (
          <Empty title="No outstanding receivables" icon="payments">
            Every issued invoice is paid.
          </Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                  <th className="py-2 pr-3 pl-5 font-semibold">Customer</th>
                  {age.buckets.map((b) => (
                    <th key={b.key} className="px-3 py-2 text-right font-semibold">
                      {b.label.replace(" days late", "").replace("Not yet due", "Current")}
                    </th>
                  ))}
                  <th className="py-2 pr-5 pl-3 text-right font-semibold">Balance due</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {age.customers.map((c) => (
                  <tr key={c.customerId ?? c.name} className="align-top">
                    <td className="py-2.5 pr-3 pl-5">
                      <p className="font-semibold">{c.name}</p>
                      <p className="mt-0.5 text-meta text-ink-3">
                        {c.invoices.map((i, n) => (
                          <span key={i.id}>
                            {n > 0 && ", "}
                            <Link href={`/invoices/${i.id}`} className="font-mono text-hema hover:underline">
                              {i.number}
                            </Link>
                            {i.daysLate > 0 && <span className="text-danger"> {i.daysLate}d overdue</span>}
                          </span>
                        ))}
                      </p>
                    </td>
                    {age.buckets.map((b) => (
                      <td key={b.key} className={`px-3 py-2.5 text-right tabular-nums ${c.buckets[b.key] && b.key !== "current" ? "text-danger" : ""}`}>
                        {c.buckets[b.key] ? fmt.peso(c.buckets[b.key]) : ""}
                      </td>
                    ))}
                    <td className="py-2.5 pr-5 pl-3 text-right font-semibold tabular-nums">{fmt.peso(c.totalCentavos)}</td>
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
