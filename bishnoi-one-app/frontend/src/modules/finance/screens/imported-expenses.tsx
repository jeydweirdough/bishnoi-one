import { ReviewExports } from "@/src/modules/finance/exports/review-controls";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { FigureStrip, ListFrame, ListToolbar, StatusPill, UnderlineTabs } from "@/src/platform/ui/list-layout";
import { ExpandableTable } from "@/src/platform/ui/expandable-table";
import { Empty, PageHeader, Particulars, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { ZohoImport } from "@/src/modules/finance/import-matching/zoho-import";
import { VoidImportedExpense } from "@/src/modules/finance/petty-cash/steps";

// Zoho expense history, called Imported expenses until 2026-11-04, when the name read as the costs of
// importing goods (app/routers/imported_expenses.py; decided 2026-10-31, Plans/Plan - Q1 imports per area):
// Zoho's Q1 expenses, as read-only history. Nobody adds or edits one here, and they aren't petty cash:
// the export has no receipt files. A mistake is voided, which reverses its entry on the day it's voided.

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const PAGE = "/finance/petty-cash/imported";

type Summary = {
  id: string; number: string; status: "posted" | "void"; date: string; vendor: string; reference: string | null; lines: number; accounts: string[];
  paidFrom: string; totalCentavos: number; vatCentavos: number; withheldCentavos: number;
};
type Listing = { items: Summary[]; limited: boolean; counts: { posted: number; void: number; all: number }; totalCentavos: number };
type Detail = Summary & {
  source: { file: string; zohoId: string; by: string; at: string };
  voucher: string | null; department: string | null; personInCharge: string | null; vendorTin: string | null; amountsIncludeVat: boolean;
  netCentavos: number; paidOutCentavos: number; entryId: string | null; voidedBy: string | null; voidedAt: string | null; voidReason: string | null; canVoid: boolean;
  items: { id: string; position: number; sourceAccount: string; sourceTax: string; description: string | null; account: { code: string; name: string }; purchaseTypeLabel: string;
    vatLabel: string; withholding: string | null; netCentavos: number; vatCentavos: number; withheldCentavos: number }[];
};

const TABS = [{ key: "posted", label: "Posted" }, { key: "void", label: "Void" }, { key: "all", label: "All" }] as const;

export async function ImportedExpensesPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const q = one(sp.q).trim().slice(0, 100);
  const show = TABS.some((t) => t.key === one(sp.show)) ? one(sp.show) : "posted";
  const query = new URLSearchParams({ show });
  if (q) query.set("q", q);
  const list = await load<Listing>(`/finance/imported-expenses?${query}`);
  const canImport = (me.permissions?.includes("imports.run") ?? false) && me.dataEnvironment === "local_test";
  const href = (key: string) => `${PAGE}?${new URLSearchParams({ show: key, ...(q ? { q } : {}) })}`;
  return (
    <>
      <PageHeader title="Zoho expense history" crumbs={[{ href: "/finance/petty-cash", label: "Petty cash" }]} actions={canImport && <ZohoImport kind="expenses" />}>
        Zoho&apos;s expenses, kept as read-only history. They post to the books and reach the BIR purchase lists. Nobody adds or edits one here, and new spending still goes through petty cash or bills.
      </PageHeader>
      <ReviewExports filters={query.toString()} options={[ ["imported-expenses", "Zoho expenses: one row per expense"], ["imported-expense-lines", "Zoho expense lines"] ]} />
      <ListFrame>
        <FigureStrip figures={[{ label: "Posted", value: String(list.counts.posted) }, { label: "Total posted", value: fmt.peso(list.totalCentavos) }]} />
        <UnderlineTabs tabs={TABS.map((t) => ({ href: href(t.key), label: t.label, count: list.counts[t.key], current: show === t.key }))} />
        <ListToolbar q={q} placeholder="Search entry number, vendor or reference" keep={{ show }} />
        {list.items.length === 0 ? (
          <Empty title={q ? "No matching expenses" : "No Zoho expenses here"} icon="lists">
            {!q && canImport ? "Bring them in with Import from Zoho export." : null}
          </Empty>
        ) : (
          <ExpandableTable
            columns={[{ key: "number", label: "Entry" }, { key: "vendor", label: "Vendor" }, { key: "date", label: "Date" }, { key: "total", label: "Total", align: "right" }, { key: "status", label: "Status" }]}
            rows={list.items.map((x) => ({
              id: x.id,
              muted: x.status === "void",
              actions: <RowMenu label={`Actions for imported expense ${x.number}`} items={[{ label: "Open", icon: <ExternalLink />, href: `${PAGE}/${x.id}` }]} />,
              cells: [
                <Link key="n" href={`${PAGE}/${x.id}`} className="font-mono text-meta font-semibold text-ink hover:text-sage-deep hover:underline">{x.number}</Link>,
                <span key="v" className="min-w-0">
                  <span className="block truncate font-medium text-ink">{x.vendor || <span className="text-ink-3">No vendor in the export</span>}</span>
                  {x.reference && <span className="block truncate text-meta text-ink-3">Ref. {x.reference}</span>}
                </span>,
                <span key="d" className="text-ink-2">{fmt.dateLabel(x.date)}</span>,
                <span key="t" className="font-medium">{fmt.peso(x.totalCentavos)}</span>,
                <StatusPill key="s" tone={x.status === "void" ? "bad" : "good"}>{x.status === "void" ? "Void" : "Posted"}</StatusPill>,
              ],
              detail: (
                <p className="text-meta text-ink-2">
                  {x.accounts.join(", ")} · paid from {x.paidFrom}
                  {x.vatCentavos ? ` · VAT ${fmt.peso(x.vatCentavos)}` : ""}
                  {x.withheldCentavos ? ` · withheld ${fmt.peso(x.withheldCentavos)}` : ""}
                </p>
              ),
            }))}
          />
        )}
        {list.limited && <p className="p-4 text-meta text-ink-3">The first 200 are listed. Search to find the rest.</p>}
      </ListFrame>
    </>
  );
}

export async function ImportedExpensePage({ params }: { params: Promise<{ id: string }> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const x = await load<Detail>(`/finance/imported-expenses/${enc(id)}`);
  return (
    <>
      <PageHeader title={`Zoho expense ${x.number}`} crumbs={[{ href: "/finance/petty-cash", label: "Petty cash" }, { href: PAGE, label: "Zoho expense history" }]} actions={x.canVoid && <VoidImportedExpense id={x.id} number={x.number} />}>
        <StatusPill tone={x.status === "void" ? "bad" : "good"}>{x.status === "void" ? "Void" : "Posted"}</StatusPill>
        {x.status === "void" && <span className="ml-2 text-meta text-danger">Voided by {x.voidedBy}: {x.voidReason}</span>}
      </PageHeader>
      <p className="mb-4 rounded-[3px] bg-hema-tint px-4 py-2 text-sm text-ink">
        Imported from {x.source.file}, Zoho ID {x.source.zohoId}, by {x.source.by} on {fmt.dateLabel(x.source.at.slice(0, 10))}. No approval took place in Finance, and the export has no receipt file.{" "}
        {x.entryId && <Link href={`/finance/ledger/voucher/${x.entryId}`} className="font-semibold text-hema hover:underline">Open its journal entry</Link>}
      </p>
      <Sheet className="mb-5 px-5 py-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Particulars items={[["Vendor", x.vendor || "Not in the export"], ["TIN", x.vendorTin ?? "Not in the export"], ["Date", fmt.dateLabel(x.date)], ["Paid from", x.paidFrom]]} />
          <Particulars items={[["Reference", x.reference], ["Voucher", x.voucher], ["Department", x.department], ["Person in charge", x.personInCharge]]} />
        </div>
      </Sheet>
      <Sheet className="px-5 py-4">
        <SectionTitle icon="lists">Lines</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className="py-1.5 pr-2 font-semibold">Zoho account</th>
                <th className="px-2 py-1.5 font-semibold">Finance account</th>
                <th className="px-2 py-1.5 font-semibold">Purchase type</th>
                <th className="px-2 py-1.5 font-semibold">VAT</th>
                <th className="px-2 py-1.5 text-right font-semibold">Before VAT</th>
                <th className="py-1.5 pl-2 text-right font-semibold">VAT</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {x.items.map((ln) => (
                <tr key={ln.id}>
                  <td className="py-1.5 pr-2">{ln.sourceAccount}{ln.description && <span className="block text-meta text-ink-3">{ln.description}</span>}</td>
                  <td className="px-2 py-1.5">{ln.account.code} · {ln.account.name}</td>
                  <td className="px-2 py-1.5">{ln.purchaseTypeLabel}</td>
                  <td className="px-2 py-1.5">{ln.vatLabel}{ln.withholding && <span className="block text-meta text-ink-3">{ln.withholding}: {fmt.peso(ln.withheldCentavos)} withheld</span>}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{fmt.peso(ln.netCentavos)}</td>
                  <td className="py-1.5 pl-2 text-right tabular-nums">{fmt.peso(ln.vatCentavos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm font-semibold">Total {fmt.peso(x.totalCentavos)}{x.withheldCentavos ? ` · paid out ${fmt.peso(x.paidOutCentavos)}` : ""}</p>
      </Sheet>
    </>
  );
}
