import { cache } from "react";
import { PageHeader } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { param } from "@/src/modules/inventory/lib/labels";
import { context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { given, referenceOf } from "@/src/modules/inventory/lib/reference";
import type { Reference, ReportInfo } from "@/src/modules/inventory/lib/types";
import { listSavedReports, readSavedReport } from "@/src/platform/reports/custom-actions";
import { ReportsIndex } from "@/src/platform/reports/index-view";
import { ReportView } from "@/src/platform/reports/report-view";
import type { ReportData } from "@/src/platform/reports/types";

// Inventory's reports on the shared report kit (src/platform/reports/, decided 2026-10-24):
// the same index, filters, figures, chart and table as every module's.
// Statutory & batch control reports are fixed; operational reports can be saved as custom reports.

const reportList = cache(async () => (await loadQuery<{ reports: ReportInfo[] }>("query Reports { reports }", {}, ["reports"])).reports);

export async function ReportsPage({ searchParams }: { searchParams: Search }) {
  const group = param(await searchParams, "group");
  const { may } = await context();
  // Stock access alone opens the report-like stock screens listed here (not the reports themselves).
  if (!may("reports.view") && !may("stock.view")) return <NoAccess what="reports" />;
  const [listed, savedReports] = await Promise.all([
    may("reports.view") ? reportList() : Promise.resolve([]),
    listSavedReports("inventory"),
  ]);
  // Screens that work like reports, listed here rather than in the sidebar (decided 2026-10-28).
  const pages: ReportInfo[] = may("stock.view")
    ? [
        { key: "batch-expiry-page", title: "Batch and expiry", group: "Stock", about: "Every batch on hand across items, by expiry, with where it's kept.", dated: false, byWarehouse: true, fixed: true, href: "/inventory/reports/batch-expiry" },
        { key: "serial-lookup", title: "Serial number lookup", group: "Stock", about: "Find one serial-numbered unit: where it is and where it's been.", dated: false, byWarehouse: false, fixed: true, href: "/inventory/serials" },
        { key: "stock-movements", title: "Stock movements", group: "Activity", about: "Every movement in and out, as it happened, with its document.", dated: true, byWarehouse: true, fixed: true, href: "/inventory/movements" },
      ]
    : [];
  const reports = [...listed, ...pages];
  return (
    <>
      <PageHeader title={group ? `${group} reports` : "Reports"}>
        {reports.length} reports on stock, purchasing, orders and control. Filter by warehouse and period{may("reports.export") ? ", and export any of them to Excel" : ""}.
      </PageHeader>
      <ReportsIndex
        reports={reports}
        base="/inventory/reports"
        group={group || undefined}
        savedReports={savedReports}
      />
    </>
  );
}

export async function generateReportMetadata({ params }: { params: Params<{ key: string }> }) {
  const { key } = await params;
  const reports = await reportList();
  return { title: reports.find((r) => r.key === key)?.title ?? "Report" };
}

/** Where a cell leads: the record's list, searched for it. */
function drill(column: string, row: ReportData["rows"][number]): string | undefined {
  const v = row[column];
  if (v === null || v === undefined || v === "") return undefined;
  const q = encodeURIComponent(String(v));
  if (column === "sku") return `/inventory/products?q=${q}`;
  if (column === "product") return row.sku ? `/inventory/products?q=${encodeURIComponent(String(row.sku))}` : undefined;
  if (column === "order" && row.receipt !== undefined) return `/inventory/purchase-orders?q=${q}`;
  if (column === "order") return `/inventory/orders?q=${q}`;
  if (column === "receipt") return `/inventory/receipts?q=${q}`;
  if (column === "supplier") return `/inventory/suppliers?q=${q}`;
  if (column === "batch") return `/inventory/reports/batch-expiry?q=${q}`;
  return undefined;
}

export async function ReportPage({ params, searchParams, reportsBase = "/inventory/reports" }: { params: Params<{ key: string }>; searchParams: Search; reportsBase?: string }) {
  const { key } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("reports.view")) return <NoAccess what="reports" />;
  const s = await searchParams;
  const f = { warehouse: param(s, "warehouse"), from: param(s, "from"), to: param(s, "to") };
  const savedId = param(s, "saved");

  const [{ report: r, reference: ref }, savedReport] = await Promise.all([
    loadQuery<{ report: ReportData & { byWarehouse: boolean }; reference: Pick<Reference, "warehouses"> }>(
      `query Report($key: String!, $warehouse: String, $from: String, $to: String) { report(key: $key, warehouse: $warehouse, from: $from, to: $to) ${referenceOf("warehouses")} }`,
      { key, ...given(f) },
      ["report", "reference"],
    ),
    savedId ? readSavedReport(savedId) : null,
  ]);

  const warehouses = r.byWarehouse ? [{ key: "warehouse", label: "Warehouse", options: [{ value: "", label: "All warehouses" }, ...ref.warehouses.map((w) => ({ value: w.id, label: w.name }))] }] : [];
  return (
    <>
      <PageHeader
        crumbs={[{ href: reportsBase, label: "Reports" }]}
        title={savedReport?.name ?? r.title}
      >
        {savedReport ? `Custom report based on ${r.title}` : r.about}{" "}
        {r.dated && r.from && r.to && <span className="text-ink-3">({day(r.from)} to {day(r.to)})</span>}
      </PageHeader>
      <ReportView
        data={r}
        base={`${reportsBase}/${key}`}
        search={f}
        format={{ money: (v) => fmt.peso(v), count: (n) => fmt.count(n), date: (d) => day(d), datetime: (d) => at(d) }}
        drill={drill}
        extraFilters={warehouses}
        canExport={may("reports.export")}
        savedReport={savedReport}
        app="inventory"
      />
    </>
  );
}
