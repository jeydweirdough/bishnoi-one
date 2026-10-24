import { Download } from "lucide-react";
import Link from "next/link";
import { buttonClass } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { cache } from "react";
import { enc, loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { FilterSelect, Filters, NoAccess } from "@/src/modules/inventory/components/ui";
import { param, query } from "@/src/modules/inventory/lib/labels";
import { context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { given, referenceOf } from "@/src/modules/inventory/lib/reference";
import type { Reference, Report, ReportInfo } from "@/src/modules/inventory/lib/types";

const reportList = cache(async () => (await loadQuery<{ reports: ReportInfo[] }>("query Reports { reports }", {}, ["reports"])).reports);

export async function ReportsPage() {
  const { may } = await context();
  if (!may("reports.view")) return <NoAccess what="reports" />;
  const reports = await reportList();
  const groups = [...new Set(reports.map((r) => r.group))];
  return (
    <>
      <PageHeader title="Reports">Filter any report by warehouse{may("reports.export") ? ", and export it to a spreadsheet" : ""}.</PageHeader>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {groups.map((g) => (
          <Sheet key={g} className="px-5 pt-4 pb-3">
            <SectionTitle icon="report">{g}</SectionTitle>
            <ul className="mt-1 divide-y divide-rule">
              {reports.filter((r) => r.group === g).map((r) => (
                <li key={r.key} className="relative py-2.5">
                  <Link href={`/inventory/reports/${r.key}`} className="font-semibold text-ink after:absolute after:inset-0 hover:underline">{r.title}</Link>
                  <span className="block text-meta text-ink-3">{r.about}</span>
                </li>
              ))}
            </ul>
          </Sheet>
        ))}
      </div>
    </>
  );
}

export async function generateReportMetadata({ params }: { params: Params<{ key: string }> }) {
  const { key } = await params;
  const reports = await reportList();
  return { title: reports.find((r) => r.key === key)?.title ?? "Report" };
}

export async function ReportPage({ params, searchParams }: { params: Params<{ key: string }>; searchParams: Search }) {
  const { key } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("reports.view")) return <NoAccess what="reports" />;
  const s = await searchParams;
  const f = { warehouse: param(s, "warehouse"), from: param(s, "from"), to: param(s, "to") };
  const { report: r, reference: ref } = await loadQuery<{ report: Report; reference: Pick<Reference, "warehouses"> }>(
    `query Report($key: String!, $warehouse: String, $from: String, $to: String) { report(key: $key, warehouse: $warehouse, from: $from, to: $to) ${referenceOf("warehouses")} }`,
    { key, ...given(f) },
    ["report", "reference"],
  );

  const show = (kind: string, v: string | number | null) => {
    if (v === null || v === undefined || v === "") return <span className="text-ink-3">—</span>;
    if (kind === "money") return fmt.peso(Number(v));
    if (kind === "number") return fmt.count(Number(v));
    if (kind === "percent") return `${Math.round(Number(v) * 1000) / 10}%`;
    if (kind === "date") return day(String(v));
    if (kind === "datetime") return at(String(v));
    return String(v);
  };
  const right = (kind: string) => ["money", "number", "percent"].includes(kind);
  // Totals for the money and plain-number columns that add up meaningfully.
  const summable = r.columns.filter((c) => c.kind === "money" || (c.kind === "number" && !/days|point|per day|cover|lead/i.test(c.label)));

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/inventory/reports", label: "Reports" }]}
        title={r.title}
        actions={
          may("reports.export") && (
            <a href={`/inventory/reports/${enc(key)}/csv${query(f)}`} className={buttonClass("default")} download>
              <Download className="size-4" aria-hidden /> Export CSV
            </a>
          )
        }
      >
        {r.about} {r.dated && <span className="text-ink-3">({day(r.from)} to {day(r.to)})</span>}
      </PageHeader>
      {(r.byWarehouse || r.dated) && (
        <Filters>
          {r.byWarehouse && <FilterSelect name="warehouse" label="Warehouse" value={f.warehouse} options={[{ value: "", label: "All warehouses" }, ...ref.warehouses.map((w) => ({ value: w.id, label: w.name }))]} />}
          {r.dated && (
            <>
              <label className="block"><span className="mb-1 block text-meta font-medium text-ink-2">From</span><input type="date" name="from" defaultValue={f.from || r.from} className="h-9 border-0 border-b border-control bg-transparent text-sm" /></label>
              <label className="block"><span className="mb-1 block text-meta font-medium text-ink-2">To</span><input type="date" name="to" defaultValue={f.to || r.to} className="h-9 border-0 border-b border-control bg-transparent text-sm" /></label>
            </>
          )}
        </Filters>
      )}
      <Sheet>
        {r.rows.length === 0 ? (
          <Empty icon="report" title="No data">No records for this {r.dated ? "period" : "report"}{f.warehouse ? " in this warehouse" : ""}.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" style={{ minWidth: `${Math.max(40, r.columns.length * 8)}rem` }}>
              <thead>
                <tr className="border-b border-rule text-left text-meta text-ink-3">
                  {r.columns.map((c) => <th key={c.key} scope="col" className={`px-3 py-3 font-semibold first:pl-5 last:pr-5 ${right(c.kind) ? "text-right" : ""}`}>{c.label}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {r.rows.map((row, i) => (
                  <tr key={i} className="hover:bg-bench/40">
                    {r.columns.map((c) => (
                      <td key={c.key} className={`px-3 py-2 first:pl-5 last:pr-5 ${right(c.kind) ? "text-right whitespace-nowrap tabular-nums" : ""} ${c.kind === "datetime" ? "whitespace-nowrap text-meta text-ink-2" : ""}`}>
                        {show(c.kind, row[c.key])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              {summable.length > 0 && r.rows.length > 1 && (
                <tfoot>
                  <tr className="border-t-2 border-rule-strong font-semibold">
                    {r.columns.map((c, i) => (
                      <td key={c.key} className={`px-3 py-2 first:pl-5 last:pr-5 ${right(c.kind) ? "text-right tabular-nums" : ""}`}>
                        {summable.includes(c) ? show(c.kind, r.rows.reduce((n, row) => n + (Number(row[c.key]) || 0), 0)) : i === 0 ? "Total" : ""}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
      </Sheet>
      <p className="mt-3 text-meta text-ink-3">{r.rows.length} row{r.rows.length === 1 ? "" : "s"}.</p>
    </>
  );
}
