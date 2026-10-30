import { notFound } from "next/navigation";
import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import { ReportTable } from "@/src/platform/reports/table";
import type { Cell, ColumnKind } from "@/src/platform/reports/types";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";

type Search = Promise<Record<string, string | string[] | undefined>>;
type Report = { key: string; name: string; about: string; dated: boolean; from: string; to: string; columns: { key: string; label: string; kind: ColumnKind }[]; rows: Cell[][] };

const PERIODS = [
  { value: "month", label: "This month" },
  { value: "last-month", label: "Last month" },
  { value: "quarter", label: "This quarter" },
  { value: "year", label: "This year" },
] as const;
type Period = (typeof PERIODS)[number]["value"];

/** The period's first and last day, in Manila (YYYY-MM-DD). */
function span(period: Period): { from: string; to: string } {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date());
  const [y, m] = today.split("-").map(Number);
  const iso = (yy: number, mm: number, dd: number) => `${yy}-${String(mm).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
  const last = (yy: number, mm: number) => new Date(Date.UTC(yy, mm, 0)).getUTCDate();
  if (period === "last-month") {
    const [py, pm] = m === 1 ? [y - 1, 12] : [y, m - 1];
    return { from: iso(py, pm, 1), to: iso(py, pm, last(py, pm)) };
  }
  if (period === "quarter") return { from: iso(y, Math.floor((m - 1) / 3) * 3 + 1, 1), to: today };
  if (period === "year") return { from: iso(y, 1, 1), to: today };
  return { from: iso(y, m, 1), to: today };
}

/** One people report (2026-10-30): the Platform's rows in the shared report table (sort, search, export, print). */
export default async function PeopleReport({ params, searchParams }: { params: Promise<{ key: string }>; searchParams: Search }) {
  const { key } = await params;
  const s = await searchParams;
  const period: Period = PERIODS.some((p) => p.value === s.period) ? (s.period as Period) : "month";
  const { from, to } = span(period);
  let report: Report;
  try {
    report = await accountSend<Report>("GET", `/identity/company/reports/${encodeURIComponent(key)}?from=${from}&to=${to}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const base = `/platform/reports/people/${encodeURIComponent(key)}`;
  return (
    <>
      <PageHeader
        title={report.name}
        crumbs={[{ href: "/platform/reports", label: "Reports Center" }]}
        tools={report.dated ? <ToggleLinks current={period} options={PERIODS.map((p) => ({ ...p, href: `${base}?period=${p.value}` }))} /> : undefined}
      >
        {report.about}
        {report.dated ? ` ${report.from} to ${report.to}.` : ""}
      </PageHeader>
      <Sheet className="px-5 py-4">
        <ReportTable title={report.name} columns={report.columns} rows={report.rows} totals={null} canExport />
      </Sheet>
    </>
  );
}
