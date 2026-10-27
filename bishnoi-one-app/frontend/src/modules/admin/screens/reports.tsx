import { cache } from "react";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/admin/platform/lib/api";
import { makeFormat } from "@/src/modules/admin/platform/lib/format";
import { Restricted } from "@/src/modules/admin/components/restricted";
import { listSavedReports, readSavedReport } from "@/src/platform/reports/custom-actions";
import { ReportsIndex } from "@/src/platform/reports/index-view";
import { ReportView } from "@/src/platform/reports/report-view";
import type { ReportData, ReportInfo } from "@/src/platform/reports/types";

// Executive Admin's reports (its API's app/routers/reports.py) on the shared report kit: each
// person sees the reports for the records their role may open. Renewal reports look ahead (today
// and the next 90 days) unless another period is picked.

type Search = Promise<Record<string, string | string[] | undefined>>;
type Params = Promise<{ key: string }>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

const reportList = cache(() => load<ReportInfo[]>("/admin/reports"));

export async function ReportsPage({ searchParams }: { searchParams: Search }) {
  const group = one((await searchParams).group);
  const [reports, savedReports] = await Promise.all([
    reportList(),
    listSavedReports("admin"),
  ]);
  if (!reports.length) return <Restricted what="any reports" />;
  return (
    <>
      <PageHeader title={group ? `${group} reports` : "Reports"}>
        {reports.length} reports on renewals, fleet and travel, office requests and promotional materials. Pick a period, filter, and export to Excel.
      </PageHeader>
      <ReportsIndex
        reports={reports}
        base="/admin/reports"
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
  if (column === "vehicle" || column === "plate") return `/admin/vehicles?q=${q}`;
  if (column === "property") return `/admin/properties?q=${q}`;
  if (column === "number") return `/admin/tickets?q=${q}`;
  if (column === "material") return `/admin/materials?q=${q}`;
  if (column === "record" && row.kind === "Permit") return `/admin/permits?q=${q}`;
  if (column === "record" && row.kind === "Lease") return `/admin/properties?q=${q}`;
  return undefined;
}

export async function ReportPage({ params, searchParams, reportsBase = "/admin/reports" }: { params: Params; searchParams: Search; reportsBase?: string }) {
  const { key } = await params;
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const s = await searchParams;
  const f = { from: one(s.from), to: one(s.to) };
  const savedId = one(s.saved);
  const query = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]);

  const [r, savedReport] = await Promise.all([
    load<ReportData>(`/admin/reports/${encodeURIComponent(key)}${query.size ? `?${query}` : ""}`),
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
        app="admin"
      />
    </>
  );
}
