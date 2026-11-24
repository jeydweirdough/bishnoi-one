import { ContainedTable } from "@/src/modules/finance/bir/contained-table";
import { Select } from "@/src/platform/ui/pickers";
import { ReviewExports } from "@/src/modules/finance/exports/review-controls";
import Link from "next/link";
import type { ReactNode } from "react";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Empty, PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import type {
  AtcRow, BalanceSheet, Book, CashDisbursements, CashReceipts, GeneralJournal, GeneralLedger, IncomeStatement, IncomeTaxReturn, PurchaseJournal, SalesJournal, SummaryList, Taxpayer, VatReturn,
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

const inputClass = "ml-2 h-8 rounded-lg border border-rule-strong bg-sheet px-2 text-sm";
const buttonClass = "h-8 rounded-lg border border-rule-strong bg-sheet px-3 text-meta font-semibold hover:border-control";

function ReportTabs({ current, options }: { current: string; options: { value: string; label: string; href: string }[] }) {
  return <nav aria-label="Report sections" className="flex max-w-full flex-wrap gap-1.5 print:hidden">{options.map(o =>
    <Link key={o.value} href={o.href} aria-current={current === o.value ? "page" : undefined} className={`rounded-lg border px-3 py-2 text-meta ${current === o.value ? "border-ink bg-ink font-semibold text-white" : "border-rule bg-sheet text-ink-2 hover:border-control"}`}>{o.label}</Link>
  )}</nav>;
}

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
          <Link href="/platform/settings/finance/taxes" className="text-danger underline-offset-2 hover:underline">
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
        <Select name="year" defaultValue={year} className={inputClass}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </Select>
      </label>
      <label className="text-meta text-ink-2">
        Quarter
        <Select name="quarter" defaultValue={quarter} className={inputClass}>
          {[1, 2, 3, 4].map((q) => (
            <option key={q} value={q}>
              {["1st", "2nd", "3rd", "4th"][q - 1]}
            </option>
          ))}
        </Select>
      </label>
      <button suppressHydrationWarning type="submit" className={buttonClass}>
        Show
      </button>
    </form>
  );
}

function Toolbar({ children, file, datFile }: { children: ReactNode; file?: string; datFile?: string }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      {children}
      {(file || datFile) && (
        <div className="flex flex-wrap items-center gap-2">
          {file && (
            <a href={file} className={buttonClass + " inline-flex items-center"}>
              Download CSV
            </a>
          )}
          {datFile && (
            <a href={datFile} className="inline-flex h-8 items-center rounded-[3px] border border-ink bg-ink px-3 text-meta font-semibold text-white hover:bg-ink/90">
              Download .DAT (draft)
            </a>
          )}
        </div>
      )}
    </div>
  );
}

const th = "px-3 py-2.5 font-semibold first:pl-5 last:pr-5";
const td = "px-3 py-2 first:pl-5 last:pr-5";
const num = "text-right tabular-nums";

const Table = ContainedTable;

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
        <ReportTabs current={book} options={BOOKS.map((b) => ({ value: b.value, label: b.label, href: `/finance/bir?book=${b.value}&${keepDates}` }))} />
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
          <td className={`${td} ${num}`}>{r.cwtCentavos ? `${fmt.peso(r.cwtCentavos)} (${r.atc ?? "ATC not in Oojeema's file"})` : ""}</td>
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
      grouped
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
        <div className="flex flex-wrap gap-2">
          <a href={download(`/finance/bir/statements/income?start=${inc.period.start}&end=${inc.period.end}&format=csv`)} className={buttonClass + " inline-flex items-center"}>
            Income statement (CSV)
          </a>
          <a href={download(`/finance/bir/statements/balance?asOf=${bs.asOf}&format=csv`)} className={buttonClass + " inline-flex items-center"}>
            Balance sheet (CSV)
          </a>
        </div>
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
      <Sheet className="mb-4 flex flex-wrap items-center justify-between gap-4 px-4 py-3 print:hidden">
        <QuarterForm action="/finance/bir/vat" year={vat.year} quarter={vat.quarter} />
        {isVat && (
          <Link className={primaryPdfBtn} href={`/finance/bir/vat/draft?year=${vat.year}&quarter=${vat.quarter}`}>
            Download 2550Q official draft PDF
          </Link>
        )}
      </Sheet>
      <div className="space-y-5">
        <section className="min-w-0">
          <h2 className="mb-2 text-base font-semibold text-ink">Monthly breakdown</h2>
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
        </section>
        <section className="min-w-0">
          <h2 className="mb-2 text-base font-semibold text-ink">Return figures</h2>
          <Table wide="min-w-[28rem]" head={[{ label: "Return item" }, { label: "Amount", right: true }]}>
            {vat.lines.map((l) => (
              <tr key={l.key} className={l.key === "payable" || l.key === "due" ? "border-t-2 border-ink font-semibold" : ""}>
                <td className={td}>{l.label}</td>
                <td className={`${td} ${num}`}>{l.rateBp !== undefined ? `${(l.rateBp / 100).toFixed(2)}%` : fmt.peso(l.amountCentavos ?? 0)}</td>
              </tr>
            ))}
          </Table>
          {vat.notes.map((n) => (
            <p key={n} className="px-5 pt-2 pb-1 text-meta text-ink-3">{n}</p>
          ))}
        </section>
        {isVat && <FilingNotice form="2550Q" />}
        <ReviewExports dates={false} filters={`year=${vat.year}&quarter=${vat.quarter}`} options={[["vat", "Return figures and monthly breakdown"], ["vat-sources", "Records behind the VAT figures"]]} />
      </div>
    </>
  );
}

export async function BirIncomeTaxPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const q = new URLSearchParams();
  if (/^\d{4}$/.test(one(sp.year))) q.set("year", one(sp.year));
  if (/^[1-4]$/.test(one(sp.quarter))) q.set("quarter", one(sp.quarter));
  const rateBp = one(sp.rateBp) === "2000" ? 2000 : 2500;
  q.set("rateBp", String(rateBp));
  const apiPath = `/finance/bir/returns/income-tax?${q}`;
  const data = await load<IncomeTaxReturn>(apiPath);
  const years = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
  return (
    <>
      <PageHeader title={`${data.title} (BIR Form ${data.form})`}>
        Draft calculation for {data.period.label} ({fmt.dateLabel(data.period.start)} to {fmt.dateLabel(data.period.end)}) from the Income Statement and Customer CWT (SAWT). Confirm non-deductible expenses and CREATE 20% eligibility with Compliance before filing.
      </PageHeader>
      <TaxpayerLine who={data.taxpayer} />
      <Sheet className="mb-4 flex flex-wrap items-end justify-between gap-4 px-4 py-3 print:hidden">
        <form className="flex flex-wrap items-end gap-3" action="/finance/bir/income-tax">
          <label className="text-meta text-ink-2">
            Year
            <select suppressHydrationWarning name="year" defaultValue={data.year} className={inputClass}>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>
          <label className="text-meta text-ink-2">
            Quarter
            <select suppressHydrationWarning name="quarter" defaultValue={data.quarter} className={inputClass}>
              {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{["1st", "2nd", "3rd", "4th"][n - 1]}</option>)}
            </select>
          </label>
          <label className="text-meta text-ink-2">
            Corporate rate
            <select suppressHydrationWarning name="rateBp" defaultValue={rateBp} className={inputClass}>
              <option value="2500">25% Standard RCIT</option>
              <option value="2000">20% CREATE Small Corp</option>
            </select>
          </label>
          <button suppressHydrationWarning type="submit" className={buttonClass}>Show</button>
        </form>
        <a href={download(apiPath)} className={secondaryCsvBtn}>
          Download 1702Q working CSV
        </a>
      </Sheet>
      <div className="space-y-5">
        <Table wide="min-w-[32rem]" head={[{ label: "1702Q working item" }, { label: "Amount", right: true }]}>
          {data.lines.map((l) => (
            <tr key={l.key} className={l.key === "net_payable" || l.key === "tax_due" || l.key === "gross_income" ? "border-t border-ink/40 font-semibold" : ""}>
              <td className={td}>{l.label}</td>
              <td className={`${td} ${num}`}>{fmt.peso(l.amountCentavos)}</td>
            </tr>
          ))}
        </Table>
        {data.notes.map((n) => (
          <p key={n} className="text-meta text-ink-3">{n}</p>
        ))}
        <FilingNotice form="1702Q" />
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
        <ReportTabs
          current={which}
          options={[
            { value: "sls", label: "Sales (SLS)", href: `/finance/bir/lists?list=sls&${keep}` },
            { value: "slp", label: "Purchases (SLP)", href: `/finance/bir/lists?list=slp&${keep}` },
            { value: "sawt", label: "Withheld by customers (SAWT)", href: `/finance/bir/lists?list=sawt&${keep}` },
            { value: "qap", label: "Withheld from suppliers (QAP)", href: `/finance/bir/lists?list=qap&${keep}` },
          ]}
        />
      </div>
      <Toolbar file={download(path)} datFile={download(`${path}${path.includes("?") ? "&" : "?"}format=dat`)}>
        <QuarterForm action="/finance/bir/lists" year={data.year} quarter={data.quarter} keep={{ list: which }} />
      </Toolbar>
      {data.missingTin > 0 && (
        <p className="mb-3 text-meta text-danger">
          {data.missingTin} {data.missingTin === 1 ? "line has" : "lines have"} no TIN. {which === "sls"
            ? "Review the affected sales with BIR Compliance before filing; buyer-detail requirements depend on the transaction."
            : which === "sawt"
              ? "Check the withholding agent's details against the supporting certificate with BIR Compliance before claiming the tax credit."
              : "Check supplier or payee details against the supporting documents with BIR Compliance before filing."}
          {" "}Keep unknown TINs blank; do not invent one. Use the approved correction process for an existing record rather than making the bill again.
        </p>
      )}
      <p className="mb-3 text-meta text-ink-3">
        The CSV matches the BIR template&apos;s columns. The draft .DAT file follows public BIR RELIEF / Alphalist formatting — verify it inside the official BIR Validation Module before eSubmission.
      </p>
      {data.rows.length === 0 ? (
        <Sheet>
          <Empty title={LIST_EMPTY[which][0]} icon="lists">
            {LIST_EMPTY[which][1]}
          </Empty>
        </Sheet>
      ) : which === "slp" ? (
        <Table
          wide="min-w-[110rem]"
          head={[{ label: "TIN" }, { label: "Registered name" }, { label: "Exempt", right: true }, { label: "Zero-rated", right: true }, { label: "Taxable", right: true }, { label: "Input tax", right: true }, { label: "Gross taxable", right: true }, ...["Services", "Services VAT", "Capital goods", "Capital goods VAT", "Other goods", "Other goods VAT", "Importation", "Importation VAT"].map((label) => ({ label, right: true }))]}
          foot={
            <tr className="border-t-2 border-ink font-semibold tabular-nums">
              <td className={td} colSpan={2}>Total</td>
              {["exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "inputTaxCentavos", "grossTaxableCentavos", "servicesCentavos", "servicesInputTaxCentavos", "capitalGoodsCentavos", "capitalGoodsInputTaxCentavos", "otherGoodsCentavos", "otherGoodsInputTaxCentavos", "importationCentavos", "importationInputTaxCentavos"].map((k) => (
                <td key={k} className={`${td} ${num}`}>{fmt.peso(n(data.totals[k]))}</td>
              ))}
            </tr>
          }
        >
          {data.rows.map((r, i) => (
            <tr key={i}>
              <td className={td}>{(r.tin as string) || <span className="text-danger">None</span>}</td>
              <td className={td}>{r.name as string}</td>
              {["exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "inputTaxCentavos", "grossTaxableCentavos", "servicesCentavos", "servicesInputTaxCentavos", "capitalGoodsCentavos", "capitalGoodsInputTaxCentavos", "otherGoodsCentavos", "otherGoodsInputTaxCentavos", "importationCentavos", "importationInputTaxCentavos"].map((k) => (
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
              <td className={td}>{(r.atc as string) || <span className="text-ink-3">ATC not in Oojeema&apos;s file</span>}</td>
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

const primaryPdfBtn = "inline-flex h-9 items-center gap-2 rounded-lg bg-ink px-4 text-meta font-semibold text-white shadow-sm transition-colors hover:bg-ink/90";
const secondaryCsvBtn = "inline-flex h-9 items-center gap-2 rounded-lg border border-rule-strong bg-sheet px-3.5 text-meta font-semibold text-ink transition-colors hover:border-control hover:bg-bench/30";

async function FilingNotice({ form }: { form: string }) {
  const g = await load<{ online: string; attachments: string; kind: string }>(`/finance/bir/filing-guidance?form=${encodeURIComponent(form)}`);
  return (
    <section className="rounded-xl border border-rule bg-sheet px-4 py-3 print:hidden">
      <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2 text-meta">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="inline-flex items-center rounded-full bg-bench px-2.5 py-0.5 font-semibold text-ink">Draft for review</span>
          <span className="text-ink-2">Online validation: <strong className="font-medium text-ink">not verified</strong></span>
          <span className="text-ink-2">Filing evidence: <strong className="font-medium text-ink">not recorded here</strong></span>
        </div>
        <span className="text-ink-3">Missing filing details and actual payments stay unresolved</span>
      </div>
      <details className="mt-2 text-meta text-ink-2">
        <summary className="cursor-pointer font-semibold text-hema hover:underline">How to validate and file {form}</summary>
        <p className="mt-2 leading-relaxed">{g.online}</p>
        <p className="mt-1 leading-relaxed">{g.attachments}</p>
      </details>
    </section>
  );
}

function WithholdingPdfButton({ form, year, quarter, month, supplierId, label }: { form: string; year: number; quarter?: number; month?: number; supplierId?: string; label?: string }) {
  const q = new URLSearchParams({ form, year: String(year) });
  if (quarter) q.set("quarter", String(quarter));
  if (month) q.set("month", String(month));
  if (supplierId) q.set("supplierId", supplierId);
  return (
    <Link href={`/finance/bir/withholding/draft?${q}`} className={primaryPdfBtn}>
      {label ?? `Download ${form.toUpperCase()} official draft PDF`}
    </Link>
  );
}

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
          <td className={`${td} font-mono font-semibold text-ink`}>{r.atc}</td>
          <td className={td}>{r.nature ?? ""}</td>
          <td className={`${td} ${num}`}>{fmt.peso(r.baseCentavos)}</td>
          <td className={`${td} ${num}`}>{(r.rateBp / 100).toFixed(2)}%</td>
          <td className={`${td} ${num} font-medium`}>{fmt.peso(r.taxCentavos)}</td>
        </tr>
      ))}
    </Table>
  );
}

function MonthForm({ year, month }: { year: number; month: number }) {
  const years = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() - i);
  const names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return (
    <form className="flex flex-wrap items-center gap-3" action="/finance/bir/withholding">
      <input suppressHydrationWarning type="hidden" name="form" value="0619e" />
      <label className="flex items-center gap-1.5 text-meta font-medium text-ink-2">
        Year
        <Select name="year" defaultValue={year} className={inputClass}>
          {years.map((y) => <option key={y} value={y}>{y}</option>)}
        </Select>
      </label>
      <label className="flex items-center gap-1.5 text-meta font-medium text-ink-2">
        Month
        <Select name="month" defaultValue={month} className={inputClass}>
          {names.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </Select>
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
  const tabs = <ReportTabs current={form} options={FORMS.map((f) => {
    const query = new URLSearchParams({ form: f.value });
    if (/^\d{4}$/.test(one(sp.year))) query.set("year", one(sp.year));
    const month = Number(one(sp.month)), quarter = Number(one(sp.quarter));
    if (f.value === "0619e") {
      if (month >= 1 && month <= 12) query.set("month", String(month));
      else if (quarter >= 1 && quarter <= 4) query.set("month", String((quarter - 1) * 3 + 1));
    } else if (f.value !== "1604e") {
      if (quarter >= 1 && quarter <= 4) query.set("quarter", String(quarter));
      else if (month >= 1 && month <= 12) query.set("quarter", String(Math.ceil(month / 3)));
    }
    return { value: f.value, label: f.label, href: `/finance/bir/withholding?${query}` };
  })} />;
  const header = (title: string, says: ReactNode, who: Taxpayer) => (
    <>
      <PageHeader title={title}>{says}</PageHeader>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        {tabs}
        <div className="[&_p]:mb-0">
          <TaxpayerLine who={who} />
        </div>
      </div>
    </>
  );

  if (form === "0619e") {
    const q = new URLSearchParams();
    if (/^\d{4}$/.test(one(sp.year))) q.set("year", one(sp.year));
    if (/^\d{1,2}$/.test(one(sp.month))) q.set("month", one(sp.month));
    const d = await load<Withholding0619E>(`/finance/bir/withholding/0619e${q.size ? `?${q}` : ""}`);
    return (
      <>
        {header("Withholding tax", <>Monthly remittance (BIR Form 0619E) for {d.period.label}: the expanded withholding on bills dated in the month. Filed for the quarter&apos;s first two months; the third is on the 1601EQ.</>, d.taxpayer)}
        <Sheet className="mb-4 flex flex-wrap items-center justify-between gap-4 px-4 py-3 print:hidden">
          <MonthForm year={d.year} month={d.month} />
          <div className="flex flex-wrap items-center gap-2.5">
            <WithholdingPdfButton form="0619e" year={d.year} month={d.month} />
          </div>
        </Sheet>
        <div className="space-y-4">
          <AtcTable rows={d.rows} fmt={fmt} total={d.totalCentavos} />
          <FilingNotice form="0619E" />
          <ReviewExports dates={false} filters={`year=${d.year}&month=${d.month}`} options={[["0619e", "Monthly withholding review"], ["withholding-sources", "Records behind monthly withholding"]]} />
        </div>
      </>
    );
  }

  if (form === "1601eq") {
    const d = await load<Withholding1601EQ>(`/finance/bir/withholding/1601eq${quarterQuery(sp)}`);
    return (
      <>
        {header("Withholding tax", <>Quarterly return of expanded withholding (BIR Form 1601EQ), {d.period.label}. The Quarterly Alphalist of Payees (QAP) goes with it: under Summary lists.</>, d.taxpayer)}
        <Sheet className="mb-4 flex flex-wrap items-center justify-between gap-4 px-4 py-3 print:hidden">
          <QuarterForm action="/finance/bir/withholding" year={d.year} quarter={d.quarter} keep={{ form: "1601eq" }} />
          <div className="flex flex-wrap items-center gap-2.5">
            <a href={download(`/finance/bir/lists/qap?year=${d.year}&quarter=${d.quarter}`)} className={secondaryCsvBtn}>
              Download QAP CSV
            </a>
            <WithholdingPdfButton form="1601eq" year={d.year} quarter={d.quarter} />
          </div>
        </Sheet>
        <div className="space-y-4">
          <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] xl:items-start">
            <AtcTable rows={d.rows} fmt={fmt} total={d.totalCentavos} />
            <Sheet className="min-w-0 overflow-x-auto">
              <div className="border-b border-rule px-5 py-3">
                <h2 className="text-sm font-semibold text-ink">Quarterly remittance summary</h2>
              </div>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-rule">
                  <tr><td className={td}>Total withheld for the quarter</td><td className={`${td} ${num} font-medium`}>{fmt.peso(d.totalCentavos)}</td></tr>
                  {d.remitted.map((r) => (
                    <tr key={r.label}><td className={`${td} text-ink-2`}>Withheld in {r.label} (computed from books)</td><td className={`${td} ${num}`}>{fmt.peso(r.calculatedWithholdingCentavos)}</td></tr>
                  ))}
                  <tr className="border-t-2 border-ink font-semibold"><td className={td}>Remaining payable</td><td className={`${td} ${num}`}>{d.dueCentavos === null ? "Not verified" : fmt.peso(d.dueCentavos)}</td></tr>
                </tbody>
              </table>
              {d.notes.map((n) => <p key={n} className="border-t border-rule bg-bench/25 px-5 py-3 text-meta text-ink-3">{n}</p>)}
            </Sheet>
          </div>
          <FilingNotice form="1601EQ" />
          <ReviewExports dates={false} filters={`year=${d.year}&quarter=${d.quarter}`} options={[["1601eq", "Quarterly withholding review"], ["withholding-sources", "Records behind quarterly withholding"]]} />
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
        {header("Withholding tax", <>Annual information return of expanded withholding (BIR Form 1604E) for {d.year}, with its alphalist of payees.</>, d.taxpayer)}
        <Sheet className="mb-4 flex flex-wrap items-center justify-between gap-4 px-4 py-3 print:hidden">
          <form className="flex flex-wrap items-center gap-3" action="/finance/bir/withholding">
            <input suppressHydrationWarning type="hidden" name="form" value="1604e" />
            <label className="flex items-center gap-1.5 text-meta font-medium text-ink-2">
              Year
              <Select name="year" defaultValue={d.year} className={inputClass}>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </Select>
            </label>
            <button suppressHydrationWarning type="submit" className={buttonClass}>Show</button>
          </form>
          <div className="flex flex-wrap items-center gap-2.5">
            <a href={download(`/finance/bir/withholding/1604e?year=${d.year}`)} className={secondaryCsvBtn}>
              Download Alphalist CSV
            </a>
            <WithholdingPdfButton form="1604e" year={d.year} />
          </div>
        </Sheet>
        <div className="space-y-4">
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
                  <td className={`${td} font-mono text-meta`}>{r.tin || <span className="text-danger">None</span>}</td>
                  <td className={`${td} font-medium`}>{r.payee}</td>
                  <td className={`${td} font-mono`}>{r.atc}</td>
                  <td className={`${td} ${num}`}>{fmt.peso(r.baseCentavos)}</td>
                  <td className={`${td} ${num} font-medium`}>{fmt.peso(r.taxCentavos)}</td>
                </tr>
              ))}
            </Table>
          )}
          <FilingNotice form="1604E" />
        </div>
      </>
    );
  }

  // 2307: the suppliers withheld from in the quarter, and the certificate for the one picked.
  const q = new URLSearchParams(quarterQuery(sp).slice(1));
  if (one(sp.supplierId)) q.set("supplierId", one(sp.supplierId));
  let d = await load<Withholding2307>(`/finance/bir/withholding/2307${q.size ? `?${q}` : ""}`);
  if (!d.certificate && d.suppliers.length > 0 && !one(sp.supplierId)) {
    const autoQ = new URLSearchParams(q);
    autoQ.set("supplierId", d.suppliers[0].id);
    d = await load<Withholding2307>(`/finance/bir/withholding/2307?${autoQ}`);
  }
  const keep = `form=2307&year=${d.year}&quarter=${d.quarter}`;
  const c = d.certificate;
  const totalQuarterWithheld = d.suppliers.reduce((sum, s) => sum + s.taxCentavos, 0);
  return (
    <>
      {header("Withholding tax", <>Certificates of creditable tax withheld at source (BIR Form 2307), {d.period.label}: one for each supplier you withheld from, to give them.</>, d.taxpayer)}
      <Sheet className="mb-4 flex flex-wrap items-center justify-between gap-4 px-4 py-3 print:hidden">
        <QuarterForm action="/finance/bir/withholding" year={d.year} quarter={d.quarter} keep={{ form: "2307" }} />
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-meta text-ink-2">
            <strong>{d.suppliers.length}</strong> suppliers · Total withheld: <strong className="text-ink tabular-nums">{fmt.peso(totalQuarterWithheld)}</strong>
          </span>
          {c && <WithholdingPdfButton form="2307" year={d.year} quarter={d.quarter} supplierId={c.payee.id} label={`Download 2307 PDF (${(c.payee.name ?? "Supplier").slice(0, 22)}${(c.payee.name ?? "").length > 22 ? "…" : ""})`} />}
        </div>
      </Sheet>
      {d.suppliers.length === 0 ? (
        <Sheet><Empty title="No tax withheld from suppliers this quarter" icon="lists">Bills with an ATC (expanded withholding) appear here.</Empty></Sheet>
      ) : (
        <div className="space-y-4">
          <div className="grid min-w-0 gap-5 lg:grid-cols-[20rem_minmax(0,1fr)] lg:items-start">
            <Sheet className="min-w-0 overflow-hidden">
              <div className="flex items-center justify-between border-b border-rule bg-bench/25 px-4 py-3">
                <h2 className="text-sm font-semibold text-ink">Suppliers ({d.suppliers.length})</h2>
                <span className="text-meta text-ink-3">Select to preview 2307</span>
              </div>
              <ul aria-label="Choose a supplier" className="max-h-[58vh] divide-y divide-rule overflow-y-auto overscroll-contain">
                {d.suppliers.map((s) => {
                  const active = c?.payee.id === s.id;
                  return (
                    <li key={s.id}>
                      <Link
                        href={`/finance/bir/withholding?${keep}&supplierId=${encodeURIComponent(s.id)}`}
                        aria-current={active ? "page" : undefined}
                        className={`block px-4 py-3 text-sm transition-colors ${active ? "border-l-4 border-hema bg-hema-tint/70 font-semibold text-hema" : "hover:bg-bench/30"}`}
                      >
                        <span className="block break-words leading-snug">{s.name}</span>
                        <span className="mt-1 flex items-center justify-between text-meta font-normal text-ink-3">
                          <span className="font-mono">{s.tin ? `TIN ${s.tin}` : "TIN missing"}</span>
                          <span className="font-semibold text-ink-2 tabular-nums">{fmt.peso(s.taxCentavos)}</span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </Sheet>
            {c ? (
              <Sheet className="min-w-0 overflow-x-auto px-6 py-5 print:shadow-none">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-rule pb-4">
                  <div>
                    <span className="inline-block rounded-full bg-bench px-2.5 py-0.5 text-caps font-semibold text-ink-2 uppercase">BIR Form No. 2307</span>
                    <h2 className="mt-1.5 text-lg font-semibold text-ink">{c.payee.name}</h2>
                    <p className="mt-0.5 text-meta text-ink-2">Certificate of Creditable Tax Withheld at Source · {d.period.label} ({fmt.dateLabel(d.period.start)} to {fmt.dateLabel(d.period.end)})</p>
                  </div>
                  <div className="print:hidden">
                    <WithholdingPdfButton form="2307" year={d.year} quarter={d.quarter} supplierId={c.payee.id} label="Download Form 2307 PDF" />
                  </div>
                </div>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-rule bg-bench/20 p-3.5 text-sm">
                    <p className="text-caps font-semibold text-ink-3 uppercase">Payee (Supplier)</p>
                    <p className="mt-1 font-semibold text-ink">{c.payee.name}</p>
                    <p className="mt-0.5 font-mono text-meta">TIN: {c.payee.tin ?? <span className="font-sans text-danger">Missing — add to supplier profile</span>}</p>
                    {c.payee.address && <p className="mt-1 text-meta text-ink-2">{c.payee.address}</p>}
                  </div>
                  <div className="rounded-lg border border-rule bg-bench/20 p-3.5 text-sm">
                    <p className="text-caps font-semibold text-ink-3 uppercase">Payor (Withholding Agent)</p>
                    <p className="mt-1 font-semibold text-ink">{d.taxpayer.registeredName}</p>
                    <p className="mt-0.5 font-mono text-meta">TIN: {d.taxpayer.tin ? `${d.taxpayer.tin}-${d.taxpayer.branchCode}` : "—"}</p>
                    {d.taxpayer.address && <p className="mt-1 text-meta text-ink-2">{d.taxpayer.address}</p>}
                  </div>
                </div>
                <div className="mt-5 overflow-x-auto rounded-lg border border-rule">
                  <table className="w-full min-w-[40rem] text-sm">
                    <thead className="bg-bench/30">
                      <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                        <th className={`${td} font-semibold`}>Income payment (ATC)</th>
                        {c.monthLabels.map((m) => <th key={m} className={`${td} text-right font-semibold`}>{m}</th>)}
                        <th className={`${td} text-right font-semibold`}>Total base</th>
                        <th className={`${td} text-right font-semibold`}>Tax withheld</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-rule">
                      {c.rows.map((r) => (
                        <tr key={`${r.atc}-${r.rateBp}`}>
                          <td className={td}>
                            <span className="font-medium text-ink">{r.nature}</span>{" "}
                            <span className="inline-block rounded bg-bench px-1.5 py-0.5 font-mono text-meta text-ink-2">{r.atc} · {(r.rateBp / 100).toFixed(2)}%</span>
                          </td>
                          {r.months.map((m, i) => <td key={i} className={`${td} ${num}`}>{money(fmt, m)}</td>)}
                          <td className={`${td} ${num} font-medium`}>{fmt.peso(r.baseCentavos)}</td>
                          <td className={`${td} ${num} font-semibold text-ink`}>{fmt.peso(r.taxCentavos)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t-2 border-ink bg-bench/15 font-semibold tabular-nums">
                        <td className={td} colSpan={c.monthLabels.length + 1}>Total</td>
                        <td className={`${td} ${num}`}>{fmt.peso(c.totals.baseCentavos)}</td>
                        <td className={`${td} ${num}`}>{fmt.peso(c.totals.taxCentavos)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
                <p className="mt-4 text-meta text-ink-3">
                  Download the official Form 2307 PDF above, sign it, and issue it to the supplier so they may claim the creditable withholding tax.
                </p>
              </Sheet>
            ) : (
              <Sheet className="flex min-h-[16rem] items-center justify-center p-8 text-center">
                <p className="text-sm text-ink-2">Select a supplier on the left to preview their Form 2307 certificate and download its PDF.</p>
              </Sheet>
            )}
          </div>
          <FilingNotice form="2307" />
          <ReviewExports dates={false} filters={q.toString()} options={[["2307", "2307 supporting figures"], ["withholding-sources", "Records behind the certificates"]]} />
        </div>
      )}
    </>
  );
}

// --- BIR readiness (2026-10-29): each tax list against the books for the same period ---------------

type ReadinessCheck = {
  key: string; title: string; says: string; status: "agrees" | "differs" | "not_set"; listName: string;
  listCentavos: number; booksCentavos: number | null; closingCentavos?: number; beforeClosingCentavos?: number | null; differenceCentavos: number | null; message: string | null; causes: string[];
  accounts: { id: string; code: string; name: string }[];
  otherSources: { source: string; name: string; entries: number; centavos: number; listed: { id: string; number: string; date: string; memo: string; centavos: number }[] }[];
};
// Batch A (2026-11-05): whether every local purchase says what was withheld, or why nothing was.
type WithholdingReview = {
  status: "reviewed" | "needs_review"; missingCount: number;
  missing: { kind: "bill" | "petty_cash"; id: string; label: string; line: number; date: string; centavos: number; href: string }[];
  originNotSet: { id: string; name: string; bills: number }[]; foreignLines: number; importedWithoutWithholding: number;
};
type Readiness = { checks: ReadinessCheck[]; counts: Record<"agrees" | "differs" | "not_set", number>; note: string; period: { start: string; end: string; label: string }; withholdingReview?: WithholdingReview };
const STATUS: Record<ReadinessCheck["status"], { label: string; tone: string }> = {
  agrees: { label: "Agrees with the books", tone: "bg-mint-2 text-sage-deep" },
  differs: { label: "Differs from the books", tone: "bg-due-today/10 text-due-today" },
  not_set: { label: "Can't compare yet", tone: "bg-sheet text-ink-2" },
};

export async function BirReadinessPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["start", "end"]) if (typeof sp[key] === "string" && sp[key]) query.set(key, sp[key] as string);
  const data = await load<Readiness>(`/finance/bir/readiness?${query}`);
  return (
    <>
      <PageHeader title="BIR readiness">
        Each tax list set against the books for {data.period.label}. Where they differ, a return built from the list would disagree with the ledger; the entries behind the gap are listed. Nothing is changed here.
      </PageHeader>
      <Toolbar>
        <DatesForm action="/finance/bir/readiness" start={data.period.start} end={data.period.end} />
      </Toolbar>
      <p className="mb-4 text-sm">{data.counts.agrees} agree · {data.counts.differs} differ · {data.counts.not_set} can&apos;t be compared yet</p>
      {data.checks.every(c => c.listCentavos === 0 && c.booksCentavos === 0) && <p className="mb-4 rounded-lg border border-rule bg-sheet px-4 py-3 text-sm text-ink-2">No amounts in this period. Matching zero totals do not prove that populated records are correct; choose the period you want to review.</p>}
      <Table wide="min-w-[56rem]" head={[{label:"Check"},{label:"Report",right:true},{label:"Books",right:true},{label:"Difference",right:true},{label:"Result"}]}>
        {data.checks.map(c => <tr key={c.key}>
          <td className={td + " max-w-md align-top"}><h2 className="text-sm font-semibold">{c.title}</h2><p className="mt-1 text-meta text-ink-3">{c.listName}</p>
            {c.message && <p className="mt-2 text-meta">{c.message}</p>}
            <details className="mt-2 text-meta"><summary className="cursor-pointer text-hema">Comparison details</summary><p className="mt-2">{c.says}</p><p className="mt-1 text-ink-3">Accounts: {c.accounts.map(a => a.code + " " + a.name).join(", ") || "Not set"}</p>
              {c.causes.length > 0 && <ul className="mt-2 list-disc pl-4">{c.causes.map(cause => <li key={cause}>{cause}</li>)}</ul>}
              {c.otherSources.map(o => <div key={o.source} className="mt-3"><p className="font-semibold">{o.name}: {o.entries} entries, {fmt.peso(o.centavos)}, outside the tax list</p><ul className="mt-1 space-y-1">{o.listed.map(e => <li key={e.id}><Link href={"/finance/ledger?q=" + encodeURIComponent(e.number)} className="text-hema underline">{e.number}</Link> / {fmt.dateLabel(e.date)} / {e.memo} / {fmt.peso(e.centavos)}</li>)}</ul>{o.entries > o.listed.length && <p>First {o.listed.length} shown; open Journal entries for more.</p>}</div>)}
            </details>
          </td>
          <td className={td + " " + num + " align-top whitespace-nowrap"}>{fmt.peso(c.listCentavos)}</td>
          <td className={td + " " + num + " align-top whitespace-nowrap"}>
            <div>{c.booksCentavos === null ? "Not available" : fmt.peso(c.booksCentavos)}</div>
            {c.beforeClosingCentavos != null && (
              <div className="mt-0.5 text-meta font-normal text-ink-3">Before closings: {fmt.peso(c.beforeClosingCentavos)}</div>
            )}
          </td>
          <td className={td + " " + num + " align-top whitespace-nowrap"}>
            <div>{c.differenceCentavos === null ? "Not available" : fmt.peso(c.differenceCentavos)}</div>
            {c.beforeClosingCentavos != null && (
              <div className="mt-0.5 text-meta font-normal text-ink-3">Before closings: {fmt.peso(c.listCentavos - c.beforeClosingCentavos)}</div>
            )}
          </td>
          <td className={td + " align-top"}><span className={"inline-block rounded-md px-2 py-1 text-meta font-semibold " + STATUS[c.status].tone}>{STATUS[c.status].label}</span></td>
        </tr>)}
      </Table>
      {data.withholdingReview && <WithholdingReviewPanel review={data.withholdingReview} fmt={fmt} />}
      <p className="mt-4 text-meta text-ink-3">{data.note}</p>
    </>
  );
}

/** Totals can agree while tax that should have been withheld is missing (two zeros agree): this lists the posted
 *  local lines with no withholding code and no reason, so Sir Mel reviews them instead of hunting for them. */
function WithholdingReviewPanel({ review, fmt }: { review: WithholdingReview; fmt: ReturnType<typeof makeFormat> }) {
  const done = review.status === "reviewed";
  return (
    <section className="mt-6 rounded-lg border border-rule bg-sheet p-4" aria-labelledby="withholding-review">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="withholding-review" className="text-sm font-semibold">Withholding reviewed</h2>
        <span className={"inline-block rounded-md px-2 py-1 text-meta font-semibold " + (done ? "bg-mint-2 text-sage-deep" : "bg-due-today/10 text-due-today")}>
          {done ? "Every local purchase has a decision" : `${review.missingCount + review.originNotSet.length} to review`}
        </span>
      </div>
      <p className="mt-1 text-meta text-ink-3">Posted bill lines and petty cash receipts from local suppliers need a withholding code, or a reason why none is withheld. Foreign suppliers are never withheld from ({review.foreignLines} {review.foreignLines === 1 ? "line" : "lines"} this period).</p>
      {review.missingCount > 0 && (
        <div className="mt-3 text-sm">
          <p className="font-semibold">{review.missingCount} {review.missingCount === 1 ? "line has" : "lines have"} no withholding and no reason</p>
          <ul className="mt-1 space-y-1 text-meta">
            {review.missing.map((m) => <li key={`${m.kind}-${m.id}-${m.line}`}><Link href={`/finance${m.href}`} className="text-hema underline">{m.label}</Link> · line {m.line} · {fmt.dateLabel(m.date)} · {fmt.peso(m.centavos)}</li>)}
          </ul>
          {review.missingCount > review.missing.length && <p className="mt-1 text-meta text-ink-3">First {review.missing.length} shown.</p>}
          <p className="mt-1 text-meta text-ink-3">Already posted, so they aren&apos;t changed here: a wrong one is voided and entered again.</p>
        </div>
      )}
      {review.originNotSet.length > 0 && (
        <p className="mt-3 text-sm">Suppliers with no local or foreign set: {review.originNotSet.map((s) => <Link key={s.id} href={`/finance/suppliers/${s.id}`} className="mr-2 text-hema underline">{s.name}</Link>)}</p>
      )}
      {review.importedWithoutWithholding > 0 && (
        <p className="mt-3 text-meta text-ink-3">Also: {review.importedWithoutWithholding} imported Zoho expense {review.importedWithoutWithholding === 1 ? "line has" : "lines have"} no withholding. They came in as history, without reasons.</p>
      )}
    </section>
  );
}
