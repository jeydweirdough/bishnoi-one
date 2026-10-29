import { loadLetterhead } from "@/src/platform/print/letterhead";
import { ExternalLink, Pencil, Plus, ReceiptText, Trash2, Wallet } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { deleteInvoice } from "@/src/modules/finance/invoices/actions";
import Link from "next/link";
import { LinkButton } from "@/src/modules/finance/platform/ui/button";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { InvoiceEditor } from "@/src/modules/finance/invoices/editor";
import { AddSeries, AutoInvoiceSetting, SwitchSeries } from "@/src/modules/finance/invoices/series-editor";
import { DeleteDraft, IssueInvoice, PrintButton, RecordPayment, ReissueInvoice, RemovePayment, VoidInvoice } from "@/src/modules/finance/invoices/steps";
import { STATUS_LABELS, type Ageing, type Invoice, type InvoiceStatus, type InvoiceSummary, type Series, type TaxChoices } from "@/src/modules/finance/invoices/types";
import { Amount } from "@/src/modules/finance/platform/ui/amount";
import { FigureStrip, ListFrame, ListToolbar, StatusPill, UnderlineTabs, type Figure, type PillTone } from "@/src/platform/ui/list-layout";
import { ExpandableTable } from "@/src/platform/ui/expandable-table";

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

/** The company's active bank accounts and e-wallets, for where a payment went (step 16a). */
async function banksOf(): Promise<{ id: string; name: string; kind: string }[]> {
  return load<{ items: { id: string; name: string; kind: string; isActive: boolean }[] }>("/finance/bank-accounts")
    .then((r) => r.items.filter((b) => b.isActive))
    .catch(() => []);
}

type Listing = {
  items: InvoiceSummary[];
  counts: Record<InvoiceStatus, number> & { attention: number };
  figures: { invoicedCentavos: number; invoicedLastMonthCentavos: number; collectedCentavos: number; collectedLastMonthCentavos: number };
  methods: { key: string; label: string }[];
};

/** Where an invoice stands, as one word: paid, part paid, overdue or unpaid once issued. */
function standing(i: InvoiceSummary, today: string): { tone: PillTone; label: string } {
  if (i.status === "draft") return { tone: "plain", label: "Draft" };
  if (i.status === "void") return { tone: "bad", label: "Void" };
  if (i.balanceCentavos <= 0) return { tone: "good", label: "Paid" };
  if (i.dueDate < today) return { tone: "bad", label: i.paidCentavos > 0 ? "Partly paid, overdue" : "Overdue" };
  return i.paidCentavos > 0 ? { tone: "warn", label: "Partly paid" } : { tone: "info", label: "Unpaid" };
}

/** This month against last, in words: "12% vs last month". */
function change(now: number, before: number): Figure["change"] {
  if (!before) return now ? { text: "New this month", tone: "flat" } : undefined;
  const pct = Math.round(((now - before) / before) * 100);
  return { text: `${Math.abs(pct)}% vs last month`, tone: pct > 0 ? "up" : pct < 0 ? "down" : "flat" };
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");

export async function InvoicesPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const status = one(sp.status);
  const q = one(sp.q);
  // The drafts made from deliveries that couldn't be issued by themselves (step 13).
  const attention = one(sp.attention) === "1";
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (attention) query.set("attention", "true");
  if (q) query.set("q", q);
  const [list, banks] = await Promise.all([load<Listing>(`/finance/invoices?${query}`), banksOf()]);
  const today = fmt.todayKey();
  const f = list.figures;
  const collect = may(me, "invoices.collect");
  const total = list.counts.draft + list.counts.issued + list.counts.void;
  const href = (s: string) => {
    const next = new URLSearchParams();
    if (s) next.set("status", s);
    if (q) next.set("q", q);
    const text = next.toString();
    return text ? `/finance/invoices?${text}` : "/finance/invoices";
  };
  return (
    <>
      <PageHeader
        title="Sales invoices"
        actions={
          may(me, "invoices.create") && (
            <LinkButton href="/finance/invoices/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New invoice
            </LinkButton>
          )
        }
      >
        Invoices to customers, numbered from the BIR&apos;s series when issued and posted to the books. Open a row to see its payments.
      </PageHeader>
      <ListFrame>
        <FigureStrip
          figures={[
            { label: "Invoiced this month", value: fmt.peso(f.invoicedCentavos), icon: <ReceiptText className="size-5" aria-hidden />, change: change(f.invoicedCentavos, f.invoicedLastMonthCentavos) },
            { label: "Collected this month", value: fmt.peso(f.collectedCentavos), icon: <Wallet className="size-5" aria-hidden />, change: change(f.collectedCentavos, f.collectedLastMonthCentavos) },
          ]}
        />
        <UnderlineTabs
          tabs={[
            ...TABS.map((t) => ({ href: href(t.key), label: t.label, count: t.key ? list.counts[t.key] : total, current: !attention && status === t.key })),
            ...(list.counts.attention > 0 || attention
              ? [{ href: "/finance/invoices?attention=1", label: "From deliveries to check", count: list.counts.attention, current: attention }]
              : []),
            { href: "/finance/invoices/receivables", label: "Receivables", current: false },
            { href: "/finance/invoices/zoho", label: "Zoho records", current: false },
          ]}
        />
        <ListToolbar q={q} placeholder="Search customer, number or reference" keep={{ status }} />
        {list.items.length === 0 ? (
          <Empty title={q || status ? "No matching invoices" : "No invoices yet"} icon="lists">
            {!q && !status && may(me, "invoices.create") ? "Make the first one with New invoice." : null}
          </Empty>
        ) : (
          <ExpandableTable
            columns={[
              { key: "number", label: "Number" },
              { key: "customer", label: "Customer" },
              { key: "date", label: "Date" },
              { key: "due", label: "Due date" },
              { key: "total", label: "Total", align: "right" },
              { key: "status", label: "Payment" },
            ]}
            rows={list.items.map((i) => {
              const s = standing(i, today);
              const payments = i.payments.filter((p) => !p.removedAt);
              return {
                id: i.id,
                muted: i.status === "void",
                actions: (
                  <RowMenu
                    label={`Actions for invoice ${i.number ?? `draft for ${i.customer.name}`}`}
                    items={[
                      { label: "Open", icon: <ExternalLink />, href: `/finance/invoices/${i.id}` },
                      ...(i.status === "draft" && may(me, "invoices.create")
                        ? [
                            { label: "Edit", icon: <Pencil />, href: `/finance/invoices/${i.id}?edit=1` },
                            "divider" as const,
                            { label: "Delete draft", icon: <Trash2 />, run: deleteInvoice.bind(null, i.id), danger: true, confirm: `Delete this draft invoice for ${i.customer.name}? This can't be undone.`, done: "Draft deleted" },
                          ]
                        : []),
                    ]}
                  />
                ),
                cells: [
                  <Link key="n" href={`/finance/invoices/${i.id}`} className="font-mono text-meta font-semibold text-ink hover:text-sage-deep hover:underline">
                    {i.number ?? "Draft"}
                  </Link>,
                  <span key="c" className="flex min-w-0 items-center gap-2.5">
                    <span className="grid size-8 shrink-0 place-items-center rounded-full bg-mint-2 text-[0.6875rem] font-semibold text-sage-deep" aria-hidden>{initials(i.customer.name)}</span>
                    <span className="min-w-0">
                      <span className="block truncate font-medium text-ink">{i.customer.name}</span>
                      {(i.reference || i.replaces || i.replacedBy || i.delivery) && (
                        <span className="block truncate text-meta text-ink-3">
                          {[i.delivery && `From ${i.delivery.number}`, i.reference && `Ref. ${i.reference}`, i.replaces && `Replaces ${i.replaces.number}`, i.replacedBy && `Replaced by ${i.replacedBy.number ?? "a draft"}`].filter(Boolean).join(" · ")}
                        </span>
                      )}
                    </span>
                  </span>,
                  <span key="d" className="text-ink-2">{fmt.dateLabel(i.date)}</span>,
                  <span key="u" className={i.status === "issued" && i.balanceCentavos > 0 && i.dueDate < today ? "font-medium text-danger" : "text-ink-2"}>{i.status === "issued" ? fmt.dateLabel(i.dueDate) : ""}</span>,
                  <span key="t" className="font-medium">{i.status === "draft" ? "" : fmt.peso(i.totalCentavos)}</span>,
                  <StatusPill key="s" tone={s.tone}>{s.label}</StatusPill>,
                ],
                detail:
                  i.status === "draft" ? undefined : (
                    <div className="space-y-3">
                      {payments.length === 0 ? (
                        <p className="text-meta text-ink-3">No payments recorded{i.status === "issued" ? "." : " (void)."}</p>
                      ) : (
                        <table className="w-full text-meta">
                          <thead>
                            <tr className="text-left text-ink-3">
                              <th className="py-1 pr-3 font-medium">Paid on</th>
                              <th className="px-3 py-1 font-medium">Method</th>
                              <th className="px-3 py-1 font-medium">Reference</th>
                              <th className="px-3 py-1 text-right font-medium">Tax withheld (2307)</th>
                              <th className="py-1 pl-3 text-right font-medium">Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {payments.map((p) => (
                              <tr key={p.id} className="border-t border-rule/70">
                                <td className="py-1.5 pr-3 text-ink-2">{fmt.dateLabel(p.paidOn)}</td>
                                <td className="px-3 py-1.5 text-ink-2">{p.methodLabel}</td>
                                <td className="px-3 py-1.5 text-ink-2">{p.reference ?? ""}</td>
                                <td className="px-3 py-1.5 text-right text-ink-2 tabular-nums">{p.cwtCentavos ? fmt.peso(p.cwtCentavos) : ""}</td>
                                <td className="py-1.5 pl-3 text-right font-medium tabular-nums">{fmt.peso(p.amountCentavos)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule/70 pt-3">
                        <p className="text-meta text-ink-2">
                          Total <strong className="text-ink tabular-nums">{fmt.peso(i.totalCentavos)}</strong> · Paid <strong className="text-ink tabular-nums">{fmt.peso(i.paidCentavos)}</strong> · Balance{" "}
                          <strong className={`tabular-nums ${i.balanceCentavos > 0 ? "text-danger" : "text-sage-deep"}`}>{fmt.peso(i.balanceCentavos)}</strong>
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          {collect && i.status === "issued" && i.balanceCentavos > 0 && <RecordPayment id={i.id} owed={i.balanceCentavos} methods={list.methods} org={me.org} today={today} banks={banks} />}
                          <LinkButton href={`/finance/invoices/${i.id}`}>Open invoice</LinkButton>
                        </div>
                      </div>
                    </div>
                  ),
              };
            })}
          />
        )}
      </ListFrame>
    </>
  );
}

export async function NewInvoicePage() {
  const me = await getCompanyMe();
  const [{ choices, today }, series] = await Promise.all([taxChoices(), load<SeriesList>("/finance/invoices/series")]);
  return (
    <>
      <PageHeader title="New invoice" crumbs={[{ href: "/finance/invoices", label: "Sales invoices" }]}>
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
  const [inv, letterhead] = await Promise.all([load<Invoice>(`/finance/invoices/${enc(id)}`), loadLetterhead()]);
  const crumbs = [{ href: "/finance/invoices", label: "Sales invoices" }];

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
                  <LinkButton href={`/finance/invoices/${inv.id}?edit=1`}>Edit</LinkButton>
                  <DeleteDraft id={inv.id} />
                </>
              )}
              {inv.status !== "draft" && <PrintButton />}
              {inv.status === "issued" && may(me, "invoices.void") && inv.number && <VoidInvoice id={inv.id} number={inv.number} />}
              {inv.status === "issued" && may(me, "invoices.void") && may(me, "invoices.create") && inv.number && (
                <ReissueInvoice id={inv.id} number={inv.number} />
              )}
              {inv.status === "void" && !inv.replacedBy && may(me, "invoices.create") && inv.number && <ReissueInvoice id={inv.id} number={inv.number} cancelled />}
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
        {/* Made from a delivery (step 13): where it came from, and why it still waits when it does. */}
        {inv.delivery && (
          <p className={`mb-4 rounded-[3px] px-4 py-2 text-sm text-ink ${inv.attention && inv.status === "draft" ? "bg-promo-tint" : "bg-hema-tint"}`}>
            Made from delivery{" "}
            <Link href={`/inventory/orders/${inv.delivery.id}`} className="font-mono font-semibold text-hema hover:underline">{inv.delivery.number}</Link>
            {inv.salesOrder && (
              <>
                {" "}for sales order{" "}
                <Link href={`/sales/orders/${inv.salesOrder.id}`} className="font-mono font-semibold text-hema hover:underline">{inv.salesOrder.number}</Link>
              </>
            )}
            .{inv.attention && inv.status === "draft" && <> Waiting: {inv.attention}</>}
          </p>
        )}
        {/* Cancel and reissue: on screen only; the printed invoice stays standard (decided 2026-10-22). */}
        {(inv.replaces || inv.replacedBy) && (
          <p className="mb-4 rounded-[3px] bg-hema-tint px-4 py-2 text-sm text-ink">
            {inv.replaces && (
              <>
                Replaces{" "}
                <Link href={`/finance/invoices/${inv.replaces.id}`} className="font-mono font-semibold text-hema hover:underline">
                  {inv.replaces.number}
                </Link>
                {inv.replaces.voidedAt ? `, cancelled ${fmt.dateLabel(inv.replaces.voidedAt.slice(0, 10))}` : ""}
                {inv.replaces.reason ? `: ${inv.replaces.reason}` : ""}.
              </>
            )}
            {inv.replacedBy && (
              <>
                Replaced by{" "}
                <Link href={`/finance/invoices/${inv.replacedBy.id}`} className="font-mono font-semibold text-hema hover:underline">
                  {inv.replacedBy.number ?? "a draft"}
                </Link>
                {inv.replacedBy.status === "draft" ? " (not issued yet)" : ""}.
              </>
            )}
          </p>
        )}
        {inv.status === "draft" && (
          <Sheet className="mb-5 px-5 py-4">
            <SectionTitle icon="approvals">Issue</SectionTitle>
            {inv.problem ? (
              <p className="text-sm text-danger">{inv.problem} Edit the draft to fix it.</p>
            ) : c?.warnings.length ? (
              <p className="text-sm text-danger">
                {c.warnings.join(" ")}{" "}
                <Link href="/finance/tax" className="font-semibold underline">
                  Go to Tax, Registration
                </Link>
                , then issue it.
              </p>
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
          <div className="flex items-start gap-3">
            {/* The company's logo from its letterhead (step 10); the seller's BIR registration beside it. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {letterhead?.logo && <img src={letterhead.logo} alt="" className="h-14 max-w-40 object-contain" />}
            <div>
            <p className="text-heading">{c?.seller.registeredName ?? me.org.name}</p>
            {c?.seller.tradeName && <p className="text-meta text-ink-2">{c.seller.tradeName}</p>}
            {c?.seller.address && <p className="text-meta text-ink-2">{c.seller.address}</p>}
            {c?.seller.tin && <p className="text-meta text-ink-2">{c.seller.regimeName} TIN {c.seller.tin}</p>}
            </div>
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
          <p className="mt-5 text-sm text-ink-3">The amounts appear once the problem above is fixed.</p>
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
                    {p.cwtCentavos > 0 && (
                      <span className="text-ink-2">
                        {" "}· {fmt.peso(p.cwtCentavos)} withheld ({p.cwtAtc}{p.cwtCertificate ? `, ${p.cwtCertificate}` : ""})
                      </span>
                    )}
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
            may(me, "invoices.collect") && <RecordPayment id={inv.id} owed={inv.balanceCentavos} methods={inv.methods} org={me.org} today={fmt.todayKey()} banks={await banksOf()} />
          ) : (
            <p className="text-sm text-ink-2">Paid in full.</p>
          )}
        </Sheet>
      )}
      {inv.status !== "draft" && (
        <p className="mt-3 text-meta text-ink-3 print:hidden">
          Issued by {inv.issuedBy}.{" "}
          {inv.entryId && (
            <Link href="/finance/ledger?source=invoice" className="text-hema hover:underline">
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
  const [series, { today }, automatic] = await Promise.all([
    load<SeriesList>("/finance/invoices/series"),
    taxChoices(),
    load<{ autoInvoice: "issue" | "draft" }>("/finance/invoices/automatic"),
  ]);
  return (
    <>
      <PageHeader title="Transaction number series" crumbs={[{ href: "/finance/invoices", label: "Sales invoices" }]}>
        Each series is a run of numbers the BIR authorized, from its Authority to Print. Invoices take them in order and never go past the last; when a
        series runs low, apply for the next and add it here.
      </PageHeader>
      {series.canSetup && (
        <div className="mb-4">
          <AddSeries today={today} />
        </div>
      )}
      <Sheet className="mb-4 px-5 py-4">
        <AutoInvoiceSetting value={automatic.autoInvoice} canChange={series.canSetup} />
      </Sheet>
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
      <PageHeader title="Receivables" crumbs={[{ href: "/finance/invoices", label: "Sales invoices" }]}>
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
                            <Link href={`/finance/invoices/${i.id}`} className="font-mono text-hema hover:underline">
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
