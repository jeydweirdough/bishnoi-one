import { cache } from "react";
import { PageHeader } from "@/src/modules/finance/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { listSavedReports, readSavedReport } from "@/src/platform/reports/custom-actions";
import { ReportsIndex } from "@/src/platform/reports/index-view";
import { ReportView } from "@/src/platform/reports/report-view";
import type { ReportData, ReportInfo } from "@/src/platform/reports/types";

// Finance's reports (its API's app/routers/reports.py) on the shared report kit: each person sees
// the reports for the data their role may open. The BIR's books and forms stay under Taxes.
// Fixed reports (financial statements) cannot be customised; templates can be saved as custom reports.

type Search = Promise<Record<string, string | string[] | undefined>>;
type Params = Promise<{ key: string }>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

const reportList = cache(() => load<ReportInfo[]>("/finance/reports"));

export async function ReportsPage({ searchParams }: { searchParams: Search }) {
  const group = one((await searchParams).group);
  const [reports, savedReports] = await Promise.all([
    reportList(),
    listSavedReports("finance"),
  ]);
  return (
    <>
      <PageHeader title={group ? `${group} reports` : "Reports"}>
        {reports.length} reports on sales, collections, expenses, supplier bills and the books. Pick a period and export any of them to Excel. The BIR&apos;s books and forms are under Taxes.
      </PageHeader>
      <ReportsIndex
        reports={reports}
        base="/finance/reports"
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

export async function ReportPage({ params, searchParams, reportsBase = "/finance/reports" }: { params: Params; searchParams: Search; reportsBase?: string }) {
  const { key } = await params;
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const s = await searchParams;
  const f = { from: one(s.from), to: one(s.to) };
  const savedId = one(s.saved);
  const query = new URLSearchParams(Object.entries(f).filter(([, v]) => v) as [string, string][]);

  const [r, savedReport] = await Promise.all([
    load<ReportData>(`/finance/reports/${encodeURIComponent(key)}${query.size ? `?${query}` : ""}`),
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
        canExport
        savedReport={savedReport}
        app="finance"
      />
    </>
  );
}
