import { cache } from "react";
import { PageHeader } from "@/src/modules/pharmacy/platform/ui/sheet";
import { load } from "@/src/modules/pharmacy/platform/lib/api";
import { NoAccess } from "@/src/modules/pharmacy/components/bits";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import { listSavedReports, readSavedReport } from "@/src/platform/reports/custom-actions";
import { ReportsIndex } from "@/src/platform/reports/index-view";
import { ReportView } from "@/src/platform/reports/report-view";
import type { ReportData, ReportInfo } from "@/src/platform/reports/types";

// The Pharmacy's reports (its API's app/routers/reports.py) on the shared report kit: each person
// sees the reports for the data their role may open, grouped as the sidebar has them.
// Controlled registers are fixed; operational reports can be customised.

type Params = Promise<{ key: string }>;

const reportList = cache(() => load<ReportInfo[]>("/reports"));

export async function ReportsPage({ searchParams }: { searchParams: Search }) {
  const { allowed } = await pageFor("reports.view");
  if (!allowed) return <NoAccess what="reports" />;
  const group = param(await searchParams, "group");
  const [reports, savedReports] = await Promise.all([
    reportList(),
    listSavedReports("pharmacy"),
  ]);
  return (
    <>
      <PageHeader title={group ? `${group} reports` : "Reports"}>
        {reports.length} reports on prescriptions, dispensing, sales and stock. Pick a period, filter, and export to Excel.
      </PageHeader>
      <ReportsIndex
        reports={reports}
        base="/pharmacy/reports"
        group={group || undefined}
        savedReports={savedReports}
      />
    </>
  );
}

export async function generateReportMetadata({ params }: { params: Params }) {
  const { key } = await params;
  return { title: (await reportList()).find((r) => r.key === key)?.title ?? "Report" };
}

/** Where a cell leads: the record's list, searched for it. */
function drill(column: string, row: ReportData["rows"][number]): string | undefined {
  const v = row[column];
  if (v === null || v === undefined || v === "") return undefined;
  const q = encodeURIComponent(String(v));
  if (column === "code") return `/pharmacy/medicines?q=${q}`;
  if (column === "medicine" && row.code) return `/pharmacy/medicines?q=${encodeURIComponent(String(row.code))}`;
  if (column === "lot") return `/pharmacy/batches?q=${q}`;
  if (column === "sale") return `/pharmacy/sales?q=${q}`;
  return undefined;
}

export async function ReportPage({ params, searchParams, reportsBase = "/pharmacy/reports" }: { params: Params; searchParams: Search; reportsBase?: string }) {
  const { key } = await params;
  const { fmt, allowed } = await pageFor("reports.view");
  if (!allowed) return <NoAccess what="reports" />;
  const s = await searchParams;
  const f = { from: param(s, "from"), to: param(s, "to") };
  const savedId = param(s, "saved");
  const query = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]);

  const [r, savedReport] = await Promise.all([
    load<ReportData>(`/reports/${encodeURIComponent(key)}${query.size ? `?${query}` : ""}`),
    savedId ? readSavedReport(savedId) : null,
  ]);

  const when = fmt.on({ dateStyle: "medium", timeStyle: "short" });
  return (
    <>
      <PageHeader
        crumbs={[
          { href: reportsBase, label: "Reports" },
          { href: `${reportsBase}?group=${encodeURIComponent(r.group)}`, label: r.group },
        ]}
        title={savedReport?.name ?? r.title}
      >
        {savedReport ? `Custom report based on ${r.title}` : r.about}
      </PageHeader>
      <ReportView
        data={r}
        base={`${reportsBase}/${key}`}
        search={f}
        format={{
          money: (v) => fmt.peso(v),
          count: (n) => fmt.count(n),
          date: (d) => fmt.dateLabel(d.slice(0, 10)),
          datetime: (d) => when.format(new Date(d)),
        }}
        drill={drill}
        canExport
        savedReport={savedReport}
        app="pharmacy"
      />
    </>
  );
}
