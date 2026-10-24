import Link from "next/link";
import type { ReactNode } from "react";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/finance/platform/ui/toggle-links";
import type {
  AtcRow, BalanceSheet, Book, CashDisbursements, CashReceipts, GeneralJournal, GeneralLedger, IncomeStatement, PurchaseJournal, SalesJournal, SummaryList, Taxpayer, VatReturn,
  Withholding0619E, Withholding1601EQ, Withholding1604E, Withholding2307,
} from "@/src/modules/finance/bir/types";

// The BIR's books of accounts, financial statements, VAT return and summary
// lists (decided 2026-10-24, from Oojeema's BIR features): read from what
// Finance posts, never typed in again. Each list downloads as a CSV file in the
// BIR template's columns (app/(app)/finance/bir/download).

type Search = Promise<Record<string, string | string[] | undefined>>;
type Fmt = ReturnType<typeof makeFormat>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const isDate = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);
const download = (path: string) => `/finance/bir/download?path=${encodeURIComponent(path)}`;

const BOOKS = [
  { value: "sales-journal", label: "Sales journal" },
  { value: "purchase-journal", label: "Purchase journal" },
  { value: "cash-receipts", label: "Cash receipts" },
  { value: "cash-disbursements", label: "Cash disbursements" },
  { value: "general-journal", label: "General journal" },
  { value: "general-ledger", label: "General ledger" },
] as const;

const inputClass = "ml-2 h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm";
const buttonClass = "h-8 rounded-[3px] border border-rule-strong bg-sheet px-3 text-meta font-semibold hover:border-control";

/** Who files: the registration the forms carry, and what's missing from it. */
function TaxpayerLine({ who }: { who: Taxpayer }) {
  const missing = [!who.tin && "TIN", !who.rdoCode && "RDO code", !who.address && "registered address"].filter(Boolean) as string[];
  return (
    <p className="mb-4 text-meta text-ink-2">
      <span className="font-semibold text-ink">{who.registeredName ?? "Company not registered yet"}</span>
      {who.tin && <> · TIN {who.tin}-{who.branchCode}</>}
      {who.rdoCode && <> · RDO {who.rdoCode}</>}
      {missing.length > 0 && (
        <>
          {" "}
          ·{" "}
          <Link href="/finance/tax" className="text-danger underline-offset-2 hover:underline">
            Add the {missing.join(", ")} under Tax
          </Link>
        </>
      )}
    </p>
  );
}

function DatesForm({ action, start, end, keep }: { action: string; start: string; end: string; keep?: Record<string, string> }) {
  return (
    <form className="flex flex-wrap items-end gap-3" action={action}>
      {Object.entries(keep ?? {}).map(([k, v]) => (
        <input suppressHydrationWarning key={k} type="hidden" name={k} value={v} />
      ))}
      <label className="text-meta text-ink-2">
        From
        <input suppressHydrationWarning type="date" name="start" defaultValue={start} className={inputClass} />
      </label>
      <label className="text-meta text-ink-2">
        To
        <input suppressHydrationWarning type="date" name="end" defaultValue={end} className={inputClass} />
      </label>
      <button suppressHydrationWarning type="submit" className={buttonClass}>
        Show
      </button>
    </form>
  );
}

function QuarterForm({ action, year, quarter, keep }: { action: string; year: number; quarter: number; keep?: Record<string, string> }) {
  const years = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
  return (
    <form className="flex flex-wrap items-end gap-3" action={action}>
      {Object.entries(keep ?? {}).map(([k, v]) => (
        <input suppressHydrationWarning key={k} type="hidden" name={k} value={v} />
      ))}
      <label className="text-meta text-ink-2">
        Year
        <select suppressHydrationWarning name="year" defaultValue={year} className={inputClass}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <label className="text-meta text-ink-2">
        Quarter
        <select suppressHydrationWarning name="quarter" defaultValue={quarter} className={inputClass}>
          {[1, 2, 3, 4].map((q) => (
            <option key={q} value={q}>
              {["1st", "2nd", "3rd", "4th"][q - 1]}
            </option>
          ))}
        </select>
      </label>
      <button suppressHydrationWarning type="submit" className={buttonClass}>
        Show
      </button>
    </form>
  );
}

function Toolbar({ children, file }: { children: ReactNode; file?: string }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      {children}
      {file && (
        <a href={file} className={buttonClass + " inline-flex items-center"}>
          Download CSV
        </a>
      )}
    </div>
  );
}

const th = "px-3 py-2.5 font-semibold first:pl-5 last:pr-5";
const td = "px-3 py-2 first:pl-5 last:pr-5";
const num = "text-right tabular-nums";

function Table({ head, children, foot, wide = "min-w-[48rem]" }: { head: { label: string; right?: boolean }[]; children: ReactNode; foot?: ReactNode; wide?: string }) {
  return (
    <Sheet className="overflow-x-auto">
      <table className={`w-full ${wide} text-sm`}>
        <thead>
          <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
            {head.map((h) => (
              <th key={h.label} className={`${th} ${h.right ? "text-right" : ""}`}>
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">{children}</tbody>
        {foot && <tfoot>{foot}</tfoot>}
      </table>
    </Sheet>
  );
}

const money = (fmt: Fmt, c: number) => (c ? fmt.peso(c) : "");

// ---- Books of accounts ------------------------------------------------------------------------

export async function BirBooksPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const book = BOOKS.find((b) => b.value === one(sp.book))?.value ?? "sales-journal";
  const q = new URLSearchParams();
  if (isDate(one(sp.start))) q.set("start", one(sp.start));
  if (isDate(one(sp.end))) q.set("end", one(sp.end));
  const path = `/finance/bir/books/${book}${q.size ? `?${q}` : ""}`;
  const data = await load<Book>(path);
  const keepDates = `start=${data.period.start}&end=${data.period.end}`;
  return (
    <>
      <PageHeader title="Books of accounts">
        The books the BIR asks you to keep, from your issued invoices, payments and journal entries: {data.period.label}.
      </PageHeader>
      <TaxpayerLine who={data.taxpayer} />
      <div className="mb-4">
        <ToggleLinks current={book} options={BOOKS.map((b) => ({ value: b.value, label: b.label, href: `/finance/bir?book=${b.value}&${keepDates}` }))} />
      </div>
      <Toolbar file={download(path)}>
        <DatesForm action="/finance/bir" start={data.period.start} end={data.period.end} keep={{ book }} />
      </Toolbar>
      <BookTable data={data} fmt={fmt} />
    </>
  );
}

function BookTable({ data, fmt }: { data: Book; fmt: Fmt }) {
  if (data.book === "sales-journal") return <SalesJournalTable data={data} fmt={fmt} />;
  if (data.book === "purchase-journal") return <PurchaseJournalTable data={data} fmt={fmt} />;
  if (data.book === "cash-receipts") return <CashReceiptsTable data={data} fmt={fmt} />;
  if (data.book === "cash-disbursements") return <CashDisbursementsTable data={data} fmt={fmt} />;
  if (data.book === "general-journal") return <GeneralJournalTable data={data} fmt={fmt} />;
  return <GeneralLedgerTable data={data} fmt={fmt} />;
}

function SalesJournalTable({ data, fmt }: { data: SalesJournal; fmt: Fmt }) {
  if (data.rows.length === 0) return <Sheet><Empty title="No invoices issued in this period" icon="letters" /></Sheet>;
  const t = data.totals;
  return (
    <Table
      wide="min-w-[64rem]"
      head={[{ label: "Date" }, { label: "Invoice no." }, { label: "Customer" }, { label: "TIN" }, { label: "Gross sales", right: true }, { label: "VATable sales", right: true }, { label: "Output VAT", right: true }, { label: "Zero-rated", right: true }, { label: "VAT-exempt", right: true }]}
      foot={
        <tr className="border-t-2 border-ink font-semibold tabular-nums">
          <td className={td} colSpan={4}>Total</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.grossCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.taxableSalesCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.taxCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.zeroRatedSalesCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.exemptSalesCentavos + t.nonTaxableSalesCentavos)}</td>
        </tr>
      }
    >
      {data.rows.map((r) => (
        <tr key={r.number} className={r.void ? "text-ink-3" : ""}>
          <td className={td}>{fmt.dateLabel(r.date)}</td>
          <td className={td}>{r.number}{r.void && <span className="ml-1.5 text-meta font-semibold text-danger">VOID</span>}</td>
          <td className={td}>{r.customer}</td>
          <td className={td}>{r.tin ?? <span className="text-ink-3">None</span>}</td>
          <td className={`${td} ${num}`}>{money(fmt, r.grossCentavos)}</td>
          <td className={`${td} ${num}`}>{money(fmt, r.taxableSalesCentavos)}</td>
          <td className={`${td} ${num}`}>{money(fmt, r.taxCentavos)}</td>
          <td className={`${td} ${num}`}>{money(fmt, r.zeroRatedSalesCentavos)}</td>
          <td className={`${td} ${num}`}>{money(fmt, r.exemptSalesCentavos + r.nonTaxableSalesCentavos)}</td>
        </tr>
      ))}
    </Table>
  );
}

function PurchaseJournalTable({ data, fmt }: { data: PurchaseJournal; fmt: Fmt }) {
  if (data.rows.length === 0) return <Sheet><Empty title="No supplier bills recorded in this period" icon="letters" /></Sheet>;
  const t = data.totals;
  return (
    <Table
      wide="min-w-[70rem]"
      head={[{ label: "Date" }, { label: "Bill no." }, { label: "Supplier" }, { label: "Their invoice" }, { label: "TIN" }, { label: "Total", right: true }, { label: "VATable", right: true }, { label: "Input VAT", right: true }, { label: "Zero-rated", right: true }, { label: "Exempt", right: true }, { label: "Withheld", right: true }]}
      foot={
        <tr className="border-t-2 border-ink font-semibold tabular-nums">
          <td className={td} colSpan={5}>Total</td>
          {[t.totalCentavos, t.vatableCentavos, t.inputTaxCentavos, t.zeroRatedCentavos, t.exemptCentavos, t.ewtCentavos].map((v, i) => (
            <td key={i} className={`${td} ${num}`}>{fmt.peso(v)}</td>
          ))}
        </tr>
      }
    >
      {data.rows.map((r, i) => (
        <tr key={`${r.no}-${i}`} className={r.void ? "text-ink-3" : ""}>
          <td className={td}>{fmt.dateLabel(r.date)}</td>
          <td className={td}>{r.no}{r.void && <span className="ml-1.5 text-meta font-semibold text-danger">VOID</span>}</td>
          <td className={td}>{r.supplier}</td>
          <td className={td}>{r.supplierInvoiceNo}</td>
          <td className={td}>{r.tin ?? <span className="text-ink-3">None</span>}</td>
          {[r.totalCentavos, r.vatableCentavos, r.inputTaxCentavos, r.zeroRatedCentavos, r.exemptCentavos, r.ewtCentavos].map((v, j) => (
            <td key={j} className={`${td} ${num}`}>{money(fmt, v)}</td>
          ))}
        </tr>
      ))}
    </Table>
  );
}

function CashReceiptsTable({ data, fmt }: { data: CashReceipts; fmt: Fmt }) {
  if (data.rows.length === 0) return <Sheet><Empty title="No payments received in this period" icon="payments" /></Sheet>;
  const t = data.totals;
  return (
    <Table
      head={[{ label: "Date" }, { label: "Invoice no." }, { label: "Customer" }, { label: "Reference" }, { label: "Cash received", right: true }, { label: "Tax withheld", right: true }, { label: "Accounts receivable", right: true }]}
      foot={
        <tr className="border-t-2 border-ink font-semibold tabular-nums">
          <td className={td} colSpan={4}>Total</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.cashCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.cwtCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(t.receivablesCentavos)}</td>
        </tr>
      }
    >
      {data.rows.map((r, i) => (
        <tr key={`${r.invoice}-${i}`}>
          <td className={td}>{fmt.dateLabel(r.date)}</td>
          <td className={td}>{r.invoice}</td>
          <td className={td}>{r.customer}</td>
          <td className={td}>{r.reference ?? ""}</td>
          <td className={`${td} ${num}`}>{fmt.peso(r.cashCentavos)}</td>
          <td className={`${td} ${num}`}>{r.cwtCentavos ? `${fmt.peso(r.cwtCentavos)} (${r.atc})` : ""}</td>
          <td className={`${td} ${num}`}>{fmt.peso(r.receivablesCentavos)}</td>
        </tr>
      ))}
    </Table>
  );
}

function CashDisbursementsTable({ data, fmt }: { data: CashDisbursements; fmt: Fmt }) {
  if (data.rows.length === 0) return <Sheet><Empty title="No money paid out in this period" icon="payments" /></Sheet>;
  return (
    <Table
      head={[{ label: "Date" }, { label: "Entry no." }, { label: "Particulars" }, { label: "Paid from" }, { label: "Charged to" }, { label: "Amount", right: true }]}
      foot={
        <tr className="border-t-2 border-ink font-semibold tabular-nums">
          <td className={td} colSpan={5}>Total</td>
          <td className={`${td} ${num}`}>{fmt.peso(data.totals.amountCentavos)}</td>
        </tr>
      }
    >
      {data.rows.map((r) => (
        <tr key={r.number}>
          <td className={td}>{fmt.dateLabel(r.date)}</td>
          <td className={td}>{r.number}</td>
          <td className={td}>{r.memo}</td>
          <td className={td}>{r.from}</td>
          <td className={`${td} text-meta text-ink-2`}>{r.charged.map((c) => `${c.code} ${c.account}`).join(", ")}</td>
          <td className={`${td} ${num}`}>{fmt.peso(r.amountCentavos)}</td>
        </tr>
      ))}
    </Table>
  );
}

function GeneralJournalTable({ data, fmt }: { data: GeneralJournal; fmt: Fmt }) {
  if (data.entries.length === 0) return <Sheet><Empty title="No entries in this period" icon="lists" /></Sheet>;
  return (
    <Table
      head={[{ label: "Date" }, { label: "Entry no." }, { label: "Account" }, { label: "Debit", right: true }, { label: "Credit", right: true }]}
      foot={
        <tr className="border-t-2 border-ink font-semibold tabular-nums">
          <td className={td} colSpan={3}>Total</td>
          <td className={`${td} ${num}`}>{fmt.peso(data.totals.debitCentavos)}</td>
          <td className={`${td} ${num}`}>{fmt.peso(data.totals.creditCentavos)}</td>
        </tr>
      }
    >
      {data.entries.map((e) => [
        <tr key={e.number} className="bg-bench/40">
          <td className={td}>{fmt.dateLabel(e.date)}</td>
          <td className={td}>{e.number}</td>
          <td className={`${td} font-semibold`} colSpan={3}>{e.memo}</td>
        </tr>,
        ...e.lines.map((ln, i) => (
          <tr key={`${e.number}-${i}`}>
            <td className={td} />
            <td className={td} />
            <td className={`${td} ${ln.creditCentavos ? "pl-10" : ""}`}>
              <span className="font-mono text-meta text-ink-2">{ln.code}</span> {ln.account}
            </td>
            <td className={`${td} ${num}`}>{money(fmt, ln.debitCentavos)}</td>
            <td className={`${td} ${num}`}>{money(fmt, ln.creditCentavos)}</td>
          </tr>
        )),
      ])}
    </Table>
  );
}

function GeneralLedgerTable({ data, fmt }: { data: GeneralLedger; fmt: Fmt }) {
  if (data.accounts.length === 0) return <Sheet><Empty title="No entries in this period" icon="lists" /></Sheet>;
  return (
    <div className="space-y-4">
      {data.accounts.map((a) => (
        <Table
          key={a.code}
          head={[{ label: `${a.code} ${a.account}` }, { label: "Entry no." }, { label: "Particulars" }, { label: "Debit", right: true }, { label: "Credit", right: true }, { label: "Balance", right: true }]}
          foot={
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className={td} colSpan={5}>Balance carried forward</td>
              <td className={`${td} ${num}`}>{fmt.peso(a.closingCentavos)}</td>
            </tr>
          }
        >
          <tr className="text-ink-2">
            <td className={td} colSpan={5}>Balance brought forward</td>
            <td className={`${td} ${num}`}>{fmt.peso(a.openingCentavos)}</td>
          </tr>
          {a.rows.map((r, i) => (
            <tr key={`${r.number}-${i}`}>
              <td className={td}>{fmt.dateLabel(r.date)}</td>
              <td className={td}>{r.number}</td>
              <td className={td}>{r.memo}</td>
              <td className={`${td} ${num}`}>{money(fmt, r.debitCentavos)}</td>
              <td className={`${td} ${num}`}>{money(fmt, r.creditCentavos)}</td>
              <td className={`${td} ${num}`}>{fmt.peso(r.balanceCentavos)}</td>
            </tr>
          ))}
        </Table>
      ))}
    </div>
  );
}

// ---- Financial statements -------------------------------------------------------------------

function StatementSection({ title, lines, total, totalLabel, fmt }: { title: string; lines: { code: string; account: string; amountCentavos: number }[]; total: number; totalLabel: string; fmt: Fmt }) {
  return (
    <>
      <tr>
        <td className={`${td} pt-4 text-caps font-semibold text-ink-3 uppercase`} colSpan={2}>{title}</td>
      </tr>
      {lines.length === 0 ? (
        <tr><td className={`${td} text-ink-3`} colSpan={2}>None</td></tr>
      ) : (
        lines.map((l) => (
          <tr key={`${l.code}-${l.account}`}>
            <td className={td}>{l.code && <span className="font-mono text-meta text-ink-2">{l.code}</span>} {l.account}</td>
            <td className={`${td} ${num}`}>{fmt.peso(l.amountCentavos)}</td>
          </tr>
        ))
      )}
      <tr className="border-t border-ink font-semibold">
        <td className={td}>{totalLabel}</td>
        <td className={`${td} ${num}`}>{fmt.peso(total)}</td>
      </tr>
    </>
  );
}

export async function BirStatementsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const q = new URLSearchParams();
  if (isDate(one(sp.start))) q.set("start", one(sp.start));
  if (isDate(one(sp.end))) q.set("end", one(sp.end));
  const inc = await load<IncomeStatement>(`/finance/bir/statements/income${q.size ? `?${q}` : ""}`);
  const bs = await load<BalanceSheet>(`/finance/bir/statements/balance?asOf=${inc.period.end}`);
  return (
    <>
      <PageHeader title="Financial statements">
        The income statement for {inc.period.label}, and the balance sheet as of {fmt.dateLabel(bs.asOf)}, from the journal.
      </PageHeader>
      <TaxpayerLine who={inc.taxpayer} />
      <Toolbar>
        <DatesForm action="/finance/bir/statements" start={inc.period.start} end={inc.period.end} />
      </Toolbar>
      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <Sheet className="overflow-x-auto">
          <h2 className="px-5 pt-4 text-base font-semibold text-ink">Income statement</h2>
          <table className="w-full text-sm">
            <tbody>
              <StatementSection title="Income" lines={inc.income} total={inc.totals.incomeCentavos} totalLabel="Total income" fmt={fmt} />
              <StatementSection title="Expenses" lines={inc.expenses} total={inc.totals.expensesCentavos} totalLabel="Total expenses" fmt={fmt} />
              <tr className="border-t-2 border-ink font-semibold">
                <td className={`${td} py-3`}>{inc.totals.netCentavos >= 0 ? "Net income" : "Net loss"}</td>
                <td className={`${td} ${num} py-3`}>{fmt.peso(inc.totals.netCentavos)}</td>
              </tr>
            </tbody>
          </table>
        </Sheet>
        <Sheet className="overflow-x-auto">
          <h2 className="px-5 pt-4 text-base font-semibold text-ink">Balance sheet</h2>
          <table className="w-full text-sm">
            <tbody>
              <StatementSection title="Assets" lines={bs.assets} total={bs.totals.assetsCentavos} totalLabel="Total assets" fmt={fmt} />
              <StatementSection title="Liabilities" lines={bs.liabilities} total={bs.totals.liabilitiesCentavos} totalLabel="Total liabilities" fmt={fmt} />
              <StatementSection title="Equity" lines={bs.equity} total={bs.totals.equityCentavos} totalLabel="Total equity" fmt={fmt} />
              <tr className={`border-t-2 border-ink font-semibold ${bs.totals.balanced ? "" : "text-danger"}`}>
                <td className={`${td} py-3`}>Total liabilities and equity</td>
                <td className={`${td} ${num} py-3`}>{fmt.peso(bs.totals.liabilitiesCentavos + bs.totals.equityCentavos)}</td>
              </tr>
            </tbody>
          </table>
          {!bs.totals.balanced && <p className="px-5 pb-4 text-meta text-danger">Assets don&apos;t equal liabilities and equity: review the journal entries.</p>}
        </Sheet>
      </div>
    </>
  );
}

// ---- VAT return ----------------------------------------------------------------------------

function quarterQuery(sp: Record<string, string | string[] | undefined>): string {
  const q = new URLSearchParams();
  if (/^\d{4}$/.test(one(sp.year))) q.set("year", one(sp.year));
  if (/^[1-4]$/.test(one(sp.quarter))) q.set("quarter", one(sp.quarter));
  return q.size ? `?${q}` : "";
}

export async function BirVatPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const vat = await load<VatReturn>(`/finance/bir/returns/vat${quarterQuery(sp)}`);
  const isVat = vat.form === "2550Q";
  return (
    <>
      <PageHeader title={`${vat.title} (BIR Form ${vat.form})`}>
        The figures for the return, {vat.period.label} ({fmt.dateLabel(vat.period.start)} to {fmt.dateLabel(vat.period.end)}), from your issued invoices and recorded supplier bills. File it in eBIRForms or eFPS.
      </PageHeader>
      <TaxpayerLine who={vat.taxpayer} />
      <Toolbar>
        <QuarterForm action="/finance/bir/vat" year={vat.year} quarter={vat.quarter} />
      </Toolbar>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:items-start">
        <Sheet className="overflow-x-auto">
          <h2 className="px-5 pt-4 text-base font-semibold text-ink">For the return</h2>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-rule">
              {vat.lines.map((l) => (
                <tr key={l.key} className={l.key === "payable" || l.key === "due" ? "border-t-2 border-ink font-semibold" : ""}>
                  <td className={td}>
                    {l.label}
                  </td>
                  <td className={`${td} ${num}`}>{l.rateBp !== undefined ? `${(l.rateBp / 100).toFixed(2)}%` : fmt.peso(l.amountCentavos ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {vat.notes.map((n) => (
            <p key={n} className="px-5 pb-4 text-meta text-ink-3">{n}</p>
          ))}
        </Sheet>
        <Table
          wide="min-w-[36rem]"
          head={isVat ? [{ label: "Month" }, { label: "VATable sales", right: true }, { label: "Output VAT", right: true }, { label: "Purchases", right: true }, { label: "Input VAT", right: true }] : [{ label: "Month" }, { label: "Gross sales", right: true }]}
        >
          {vat.months.map((m) => (
            <tr key={m.start}>
              <td className={td}>{m.label}</td>
              {isVat ? (
                <>
                  <td className={`${td} ${num}`}>{fmt.peso(m.taxableSalesCentavos)}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(m.taxCentavos)}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(m.purchasesCentavos ?? 0)}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(m.inputTaxCentavos ?? 0)}</td>
                </>
              ) : (
                <td className={`${td} ${num}`}>{fmt.peso(m.nonTaxableSalesCentavos)}</td>
              )}
            </tr>
          ))}
        </Table>
      </div>
    </>
  );
}

// ---- Summary lists -------------------------------------------------------------------------

const LIST_SAYS = {
  sls: "The Summary List of Sales (SLS) for the RELIEF submission: each customer's sales for the quarter, by kind.",
  slp: "The Summary List of Purchases (SLP) for the RELIEF submission: each supplier's purchases for the quarter, by kind, and the input tax.",
  sawt: "The Summary Alphalist of Withholding Taxes (SAWT): tax your customers withheld from what they paid you (their Forms 2307), attached to your return.",
  qap: "The Quarterly Alphalist of Payees (QAP): tax you withheld from your suppliers, attached to the 1601EQ.",
} as const;

const LIST_EMPTY = {
  sls: ["No sales this quarter", "Issued invoices dated in the quarter appear here."],
  slp: ["No purchases this quarter", "Recorded supplier bills dated in the quarter appear here."],
  sawt: ["No tax withheld by customers this quarter", "Record what a customer withheld when you record their payment (Form 2307)."],
  qap: ["No tax withheld from suppliers this quarter", "Bills with an ATC (expanded withholding) appear here."],
} as const;

export async function BirListsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const which = (["sls", "slp", "sawt", "qap"] as const).find((k) => k === one(sp.list)) ?? "sls";
  const path = `/finance/bir/lists/${which}${quarterQuery(sp)}`;
  const data = await load<SummaryList>(path);
  const keep = `year=${data.year}&quarter=${data.quarter}`;
  const sls = which === "sls";
  const n = (v: unknown) => (typeof v === "number" ? v : 0);
  return (
    <>
      <PageHeader title="Summary lists">
        {LIST_SAYS[which]}{" "}
        {data.period.label}.
      </PageHeader>
      <TaxpayerLine who={data.taxpayer} />
      <div className="mb-4">
        <ToggleLinks
          current={which}
          options={[
            { value: "sls", label: "Sales (SLS)", href: `/finance/bir/lists?list=sls&${keep}` },
            { value: "slp", label: "Purchases (SLP)", href: `/finance/bir/lists?list=slp&${keep}` },
            { value: "sawt", label: "Withheld by customers (SAWT)", href: `/finance/bir/lists?list=sawt&${keep}` },
            { value: "qap", label: "Withheld from suppliers (QAP)", href: `/finance/bir/lists?list=qap&${keep}` },
          ]}
        />
      </div>
      <Toolbar file={download(path)}>
        <QuarterForm action="/finance/bir/lists" year={data.year} quarter={data.quarter} keep={{ list: which }} />
      </Toolbar>
      {data.missingTin > 0 && (
        <p className="mb-3 text-meta text-danger">
          {data.missingTin} {data.missingTin === 1 ? "line has" : "lines have"} no TIN. The BIR needs one for each: {which === "sls" || which === "sawt" ? "add it to the customer in the CRM, then on the invoice" : "add it to the supplier in Inventory, then make the bill again"}.
        </p>
      )}
      <p className="mb-3 text-meta text-ink-3">
        The CSV has the BIR template&apos;s columns. The DAT file for eSubmission comes once its official layout is confirmed.
      </p>
      {data.rows.length === 0 ? (
        <Sheet>
          <Empty title={LIST_EMPTY[which][0]} icon="lists">
            {LIST_EMPTY[which][1]}
          </Empty>
        </Sheet>
      ) : which === "slp" ? (
        <Table
          wide="min-w-[60rem]"
          head={[{ label: "TIN" }, { label: "Registered name" }, { label: "Exempt", right: true }, { label: "Zero-rated", right: true }, { label: "Taxable", right: true }, { label: "Input tax", right: true }, { label: "Gross taxable", right: true }]}
          foot={
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className={td} colSpan={2}>Total</td>
              {["exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "inputTaxCentavos", "grossTaxableCentavos"].map((k) => (
                <td key={k} className={`${td} ${num}`}>{fmt.peso(n(data.totals[k]))}</td>
              ))}
            </tr>
          }
        >
          {data.rows.map((r, i) => (
            <tr key={i}>
              <td className={td}>{(r.tin as string) || <span className="text-danger">None</span>}</td>
              <td className={td}>{r.name as string}</td>
              {["exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "inputTaxCentavos", "grossTaxableCentavos"].map((k) => (
                <td key={k} className={`${td} ${num}`}>{fmt.peso(n(r[k]))}</td>
              ))}
            </tr>
          ))}
        </Table>
      ) : which === "qap" ? (
        <Table
          head={[{ label: "TIN of payee" }, { label: "Payee" }, { label: "ATC" }, { label: "Income payment", right: true }, { label: "Rate", right: true }, { label: "Tax withheld", right: true }]}
          foot={
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className={td} colSpan={3}>Total</td>
              <td className={`${td} ${num}`}>{fmt.peso(n(data.totals.baseCentavos))}</td>
              <td className={td} />
              <td className={`${td} ${num}`}>{fmt.peso(n(data.totals.taxCentavos))}</td>
            </tr>
          }
        >
          {data.rows.map((r, i) => (
            <tr key={i}>
              <td className={td}>{(r.tin as string) || <span className="text-danger">None</span>}</td>
              <td className={td}>{r.payee as string}</td>
              <td className={td} title={(r.nature as string) ?? undefined}>{r.atc as string}</td>
              <td className={`${td} ${num}`}>{fmt.peso(n(r.baseCentavos))}</td>
              <td className={`${td} ${num}`}>{`${(n(r.rateBp) / 100).toFixed(2)}%`}</td>
              <td className={`${td} ${num}`}>{fmt.peso(n(r.taxCentavos))}</td>
            </tr>
          ))}
        </Table>
      ) : sls ? (
        <Table
          wide="min-w-[60rem]"
          head={[{ label: "TIN" }, { label: "Registered name" }, { label: "Exempt", right: true }, { label: "Zero-rated", right: true }, { label: "Taxable", right: true }, { label: "Output tax", right: true }, { label: "Gross taxable", right: true }]}
          foot={
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className={td} colSpan={2}>Total</td>
              {["exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "outputTaxCentavos", "grossTaxableCentavos"].map((k) => (
                <td key={k} className={`${td} ${num}`}>{fmt.peso(n(data.totals[k]))}</td>
              ))}
            </tr>
          }
        >
          {data.rows.map((r, i) => (
            <tr key={i}>
              <td className={td}>{(r.tin as string) || <span className="text-danger">None</span>}</td>
              <td className={td}>{r.name as string}</td>
              {["exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "outputTaxCentavos", "grossTaxableCentavos"].map((k) => (
                <td key={k} className={`${td} ${num}`}>{fmt.peso(n(r[k]))}</td>
              ))}
            </tr>
          ))}
        </Table>
      ) : (
        <Table
          head={[{ label: "TIN of payor" }, { label: "Payor" }, { label: "ATC" }, { label: "Income payment", right: true }, { label: "Rate", right: true }, { label: "Tax withheld", right: true }]}
          foot={
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className={td} colSpan={3}>Total</td>
              <td className={`${td} ${num}`}>{fmt.peso(n(data.totals.incomePaymentCentavos))}</td>
              <td className={td} />
              <td className={`${td} ${num}`}>{fmt.peso(n(data.totals.withheldCentavos))}</td>
            </tr>
          }
        >
          {data.rows.map((r, i) => (
            <tr key={i}>
              <td className={td}>{(r.tin as string) || <span className="text-danger">None</span>}</td>
              <td className={td}>{r.payor as string}</td>
              <td className={td}>{r.atc as string}</td>
              <td className={`${td} ${num}`}>{fmt.peso(n(r.incomePaymentCentavos))}</td>
              <td className={`${td} ${num}`}>{r.rateBp != null ? `${(n(r.rateBp) / 100).toFixed(2)}%` : ""}</td>
              <td className={`${td} ${num}`}>{fmt.peso(n(r.withheldCentavos))}</td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}

// ---- Withholding tax: what you withheld from your suppliers ----------------------------------

const FORMS = [
  { value: "2307", label: "Form 2307 (to suppliers)" },
  { value: "0619e", label: "0619E (monthly)" },
  { value: "1601eq", label: "1601EQ (quarterly)" },
  { value: "1604e", label: "1604E (annual)" },
] as const;

function AtcTable({ rows, fmt, total }: { rows: AtcRow[]; fmt: Fmt; total: number }) {
  if (rows.length === 0) return <Sheet><Empty title="Nothing withheld in this period" icon="lists">Bills with an ATC (expanded withholding) appear here.</Empty></Sheet>;
  return (
    <Table
      wide="min-w-[44rem]"
      head={[{ label: "ATC" }, { label: "Nature of income payment" }, { label: "Tax base", right: true }, { label: "Rate", right: true }, { label: "Tax withheld", right: true }]}
      foot={
        <tr className="border-t-2 border-ink font-semibold tabular-nums">
          <td className={td} colSpan={4}>Total</td>
          <td className={`${td} ${num}`}>{fmt.peso(total)}</td>
        </tr>
      }
    >
      {rows.map((r) => (
        <tr key={`${r.atc}-${r.rateBp}`}>
          <td className={td}>{r.atc}</td>
          <td className={td}>{r.nature ?? ""}</td>
          <td className={`${td} ${num}`}>{fmt.peso(r.baseCentavos)}</td>
          <td className={`${td} ${num}`}>{(r.rateBp / 100).toFixed(2)}%</td>
          <td className={`${td} ${num}`}>{fmt.peso(r.taxCentavos)}</td>
        </tr>
      ))}
    </Table>
  );
}

function MonthForm({ year, month }: { year: number; month: number }) {
  const years = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
  const names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return (
    <form className="flex flex-wrap items-end gap-3" action="/finance/bir/withholding">
      <input suppressHydrationWarning type="hidden" name="form" value="0619e" />
      <label className="text-meta text-ink-2">
        Year
        <select suppressHydrationWarning name="year" defaultValue={year} className={inputClass}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </label>
      <label className="text-meta text-ink-2">
        Month
        <select suppressHydrationWarning name="month" defaultValue={month} className={inputClass}>
          {names.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </select>
      </label>
      <button suppressHydrationWarning type="submit" className={buttonClass}>Show</button>
    </form>
  );
}

export async function BirWithholdingPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const form = FORMS.find((f) => f.value === one(sp.form))?.value ?? "2307";
  const tabs = <ToggleLinks current={form} options={FORMS.map((f) => ({ value: f.value, label: f.label, href: `/finance/bir/withholding?form=${f.value}` }))} />;
  const header = (title: string, says: ReactNode) => (
    <>
      <PageHeader title={title}>{says}</PageHeader>
      <div className="mb-4">{tabs}</div>
    </>
  );

  if (form === "0619e") {
    const q = new URLSearchParams();
    if (/^\d{4}$/.test(one(sp.year))) q.set("year", one(sp.year));
    if (/^\d{1,2}$/.test(one(sp.month))) q.set("month", one(sp.month));
    const d = await load<Withholding0619E>(`/finance/bir/withholding/0619e${q.size ? `?${q}` : ""}`);
    return (
      <>
        {header("Withholding tax", <>Monthly remittance (BIR Form 0619E) for {d.period.label}: the expanded withholding on bills dated in the month. Filed for the quarter&apos;s first two months; the third is on the 1601EQ.</>)}
        <TaxpayerLine who={d.taxpayer} />
        <Toolbar><MonthForm year={d.year} month={d.month} /></Toolbar>
        <AtcTable rows={d.rows} fmt={fmt} total={d.totalCentavos} />
      </>
    );
  }

  if (form === "1601eq") {
    const d = await load<Withholding1601EQ>(`/finance/bir/withholding/1601eq${quarterQuery(sp)}`);
    return (
      <>
        {header("Withholding tax", <>Quarterly return of expanded withholding (BIR Form 1601EQ), {d.period.label}. The Quarterly Alphalist of Payees (QAP) goes with it: under Summary lists.</>)}
        <TaxpayerLine who={d.taxpayer} />
        <Toolbar file={download(`/finance/bir/lists/qap?year=${d.year}&quarter=${d.quarter}`)}>
          <QuarterForm action="/finance/bir/withholding" year={d.year} quarter={d.quarter} keep={{ form: "1601eq" }} />
        </Toolbar>
        <div className="space-y-5">
          <AtcTable rows={d.rows} fmt={fmt} total={d.totalCentavos} />
          <Sheet className="max-w-xl overflow-x-auto">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-rule">
                <tr><td className={td}>Total withheld for the quarter</td><td className={`${td} ${num}`}>{fmt.peso(d.totalCentavos)}</td></tr>
                {d.remitted.map((r) => (
                  <tr key={r.label}><td className={td}>Less: remitted with the 0619E for {r.label}</td><td className={`${td} ${num}`}>{fmt.peso(r.amountCentavos)}</td></tr>
                ))}
                <tr className="border-t-2 border-ink font-semibold"><td className={td}>Still due</td><td className={`${td} ${num}`}>{fmt.peso(d.dueCentavos)}</td></tr>
              </tbody>
            </table>
            {d.notes.map((n) => <p key={n} className="px-5 pb-4 text-meta text-ink-3">{n}</p>)}
          </Sheet>
        </div>
      </>
    );
  }

  if (form === "1604e") {
    const year = /^\d{4}$/.test(one(sp.year)) ? one(sp.year) : "";
    const d = await load<Withholding1604E>(`/finance/bir/withholding/1604e${year ? `?year=${year}` : ""}`);
    const years = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
    return (
      <>
        {header("Withholding tax", <>Annual information return of expanded withholding (BIR Form 1604E) for {d.year}, with its alphalist of payees.</>)}
        <TaxpayerLine who={d.taxpayer} />
        <Toolbar file={download(`/finance/bir/withholding/1604e?year=${d.year}`)}>
          <form className="flex items-end gap-3" action="/finance/bir/withholding">
            <input suppressHydrationWarning type="hidden" name="form" value="1604e" />
            <label className="text-meta text-ink-2">
              Year
              <select suppressHydrationWarning name="year" defaultValue={d.year} className={inputClass}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </label>
            <button suppressHydrationWarning type="submit" className={buttonClass}>Show</button>
          </form>
        </Toolbar>
        <div className="space-y-5">
          <AtcTable rows={d.byAtc} fmt={fmt} total={d.totals.taxCentavos} />
          {d.payees.length > 0 && (
            <Table
              head={[{ label: "TIN of payee" }, { label: "Payee" }, { label: "ATC" }, { label: "Income payments", right: true }, { label: "Tax withheld", right: true }]}
              foot={
                <tr className="border-t-2 border-ink font-semibold tabular-nums">
                  <td className={td} colSpan={3}>Total</td>
                  <td className={`${td} ${num}`}>{fmt.peso(d.totals.baseCentavos)}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(d.totals.taxCentavos)}</td>
                </tr>
              }
            >
              {d.payees.map((r, i) => (
                <tr key={i}>
                  <td className={td}>{r.tin || <span className="text-danger">None</span>}</td>
                  <td className={td}>{r.payee}</td>
                  <td className={td}>{r.atc}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(r.baseCentavos)}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(r.taxCentavos)}</td>
                </tr>
              ))}
            </Table>
          )}
        </div>
      </>
    );
  }

  // 2307: the suppliers withheld from in the quarter, and the certificate for the one picked.
  const q = new URLSearchParams(quarterQuery(sp).slice(1));
  if (one(sp.supplierId)) q.set("supplierId", one(sp.supplierId));
  const d = await load<Withholding2307>(`/finance/bir/withholding/2307${q.size ? `?${q}` : ""}`);
  const keep = `form=2307&year=${d.year}&quarter=${d.quarter}`;
  const c = d.certificate;
  return (
    <>
      {header("Withholding tax", <>Certificates of creditable tax withheld at source (BIR Form 2307), {d.period.label}: one for each supplier you withheld from, to give them.</>)}
      <TaxpayerLine who={d.taxpayer} />
      <Toolbar>
        <QuarterForm action="/finance/bir/withholding" year={d.year} quarter={d.quarter} keep={{ form: "2307" }} />
      </Toolbar>
      {d.suppliers.length === 0 ? (
        <Sheet><Empty title="No tax withheld from suppliers this quarter" icon="lists">Bills with an ATC (expanded withholding) appear here.</Empty></Sheet>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)] lg:items-start">
          <Sheet className="px-2 py-2">
            <ul>
              {d.suppliers.map((s) => (
                <li key={s.id}>
                  <Link
                    href={`/finance/bir/withholding?${keep}&supplierId=${encodeURIComponent(s.id)}`}
                    className={`block rounded-[3px] px-3 py-2 text-sm ${c?.payee.id === s.id ? "bg-hema-tint font-semibold text-hema" : "hover:bg-sheet"}`}
                  >
                    {s.name}
                    <span className="block text-meta font-normal text-ink-3">{fmt.peso(s.taxCentavos)} withheld</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Sheet>
          {c ? (
            <Sheet className="overflow-x-auto px-5 py-4 print:shadow-none">
              <h2 className="text-base font-semibold text-ink">BIR Form 2307: {c.title}</h2>
              <p className="mt-1 text-meta text-ink-2">For {d.period.label} ({fmt.dateLabel(d.period.start)} to {fmt.dateLabel(d.period.end)})</p>
              <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <p className="text-caps text-ink-3 uppercase">Payee</p>
                  <p className="font-semibold">{c.payee.name}</p>
                  <p>TIN {c.payee.tin ?? <span className="text-danger">none: add it to the supplier in Inventory</span>}</p>
                  <p className="text-ink-2">{c.payee.address}</p>
                </div>
                <div>
                  <p className="text-caps text-ink-3 uppercase">Payor</p>
                  <p className="font-semibold">{d.taxpayer.registeredName}</p>
                  <p>TIN {d.taxpayer.tin ? `${d.taxpayer.tin}-${d.taxpayer.branchCode}` : ""}</p>
                  <p className="text-ink-2">{d.taxpayer.address}</p>
                </div>
              </div>
              <table className="mt-4 w-full min-w-[40rem] text-sm">
                <thead>
                  <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                    <th className={`${td} font-semibold`}>Income payment (ATC)</th>
                    {c.monthLabels.map((m) => <th key={m} className={`${td} text-right font-semibold`}>{m}</th>)}
                    <th className={`${td} text-right font-semibold`}>Total</th>
                    <th className={`${td} text-right font-semibold`}>Tax withheld</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {c.rows.map((r) => (
                    <tr key={`${r.atc}-${r.rateBp}`}>
                      <td className={td}>{r.nature} <span className="text-ink-3">({r.atc}, {(r.rateBp / 100).toFixed(2)}%)</span></td>
                      {r.months.map((m, i) => <td key={i} className={`${td} ${num}`}>{money(fmt, m)}</td>)}
                      <td className={`${td} ${num}`}>{fmt.peso(r.baseCentavos)}</td>
                      <td className={`${td} ${num}`}>{fmt.peso(r.taxCentavos)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-ink font-semibold tabular-nums">
                    <td className={td} colSpan={c.monthLabels.length + 1}>Total</td>
                    <td className={`${td} ${num}`}>{fmt.peso(c.totals.baseCentavos)}</td>
                    <td className={`${td} ${num}`}>{fmt.peso(c.totals.taxCentavos)}</td>
                  </tr>
                </tfoot>
              </table>
              <p className="mt-4 text-meta text-ink-3">
                Fill in the official Form 2307 (eBIRForms or the BIR&apos;s PDF) with these figures, sign it, and give it to the supplier: they claim the tax as a credit.
              </p>
            </Sheet>
          ) : (
            <Sheet><Empty title="Pick a supplier" icon="lists">Their certificate for the quarter shows here.</Empty></Sheet>
          )}
        </div>
      )}
    </>
  );
}
