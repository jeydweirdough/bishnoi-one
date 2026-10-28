import { hasTotals, totalsOf } from "./totals";
import Link from "next/link";
import { ReportChartView } from "./chart";
import { applyDefinition, type SavedReport } from "./custom";
import { RememberReport } from "./index-view";
import { ReportCustomiseButton } from "./report-customise-button";
import { ReportTable } from "./table";
import type { Cell, ColumnKind, ReportData, ReportFilter } from "./types";

/** How a module writes its values: its own money, numbers and dates. */
export type ReportFormat = {
  money: (centavos: number) => string;
  count: (n: number) => string;
  date: (iso: string) => string;
  datetime: (iso: string) => string;
};

type Search = Record<string, string | undefined>;

const iso = (d: Date) => d.toISOString().slice(0, 10);

/** The periods offered at a click, worked out from today. */
function presets(today: Date): { label: string; from: string; to: string }[] {
  const y = today.getUTCFullYear();
  const m = today.getUTCMonth();
  const q = Math.floor(m / 3);
  const day = (yy: number, mm: number, dd: number) => new Date(Date.UTC(yy, mm, dd));
  const back = (n: number) => new Date(today.getTime() - n * 86_400_000);
  return [
    { label: "Last 30 days", from: iso(back(29)), to: iso(today) },
    { label: "This month", from: iso(day(y, m, 1)), to: iso(today) },
    { label: "Last month", from: iso(day(y, m - 1, 1)), to: iso(day(y, m, 0)) },
    { label: "This quarter", from: iso(day(y, q * 3, 1)), to: iso(today) },
    { label: "Last quarter", from: iso(day(y, q * 3 - 3, 1)), to: iso(day(y, q * 3, 0)) },
    { label: "This year", from: iso(day(y, 0, 1)), to: iso(today) },
    { label: "Last year", from: iso(day(y - 1, 0, 1)), to: iso(day(y - 1, 11, 31)) },
  ];
}

const withQuery = (base: string, q: Search) => {
  const p = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
  const s = p.toString();
  return s ? `${base}?${s}` : base;
};

const numeric = (k: ColumnKind) => k === "money" || k === "number" || k === "percent";

/** Columns whose total means something: money, and counts that aren't rates, days or levels. */
// What adds up, and how a percentage is totalled: src/platform/reports/totals.ts.

/**
 * One report, as every module shows it: the period (presets and dates) and its filters at
 * the top, the headline figures, the chart, then the rows (sortable, searchable, totalled,
 * each leading to its record), with export and print. Drawn on the server in the module's
 * formats; only the table's sorting and searching run in the browser.
 */
export function ReportView({
  data,
  base,
  search,
  format,
  drill,
  extraFilters = [],
  canExport,
  savedReport,
  app,
}: {
  data: ReportData;
  /** This report's own address (/inventory/reports/valuation). */
  base: string;
  search: Search;
  format: ReportFormat;
  /** Where a cell leads: its record, or a list filtered to it. */
  drill?: (column: string, row: ReportData["rows"][number]) => string | undefined;
  /** Filters the page adds itself (Inventory's warehouses). */
  extraFilters?: ReportFilter[];
  canExport: boolean;
  savedReport?: SavedReport | null;
  app?: string;
}) {
  const mod = app ?? base.split("/").filter(Boolean)[0] ?? "crm";
  const effective = savedReport ? applyDefinition(data, savedReport.definition, savedReport.name) : data;

  const show = (kind: ColumnKind, v: string | number | null): string => {
    if (v === null || v === undefined || v === "") return "";
    if (kind === "money") return format.money(Number(v));
    if (kind === "number") return format.count(Number(v));
    if (kind === "percent") return `${Math.round(Number(v) * 1000) / 10}%`;
    if (kind === "date") return format.date(String(v));
    if (kind === "datetime") return format.datetime(String(v));
    return String(v);
  };

  const filters = [...extraFilters, ...(data.filters ?? [])];
  const rows: Cell[][] = effective.rows.map((r) =>
    effective.columns.map((c) => ({ raw: r[c.key] ?? null, text: show(c.kind, r[c.key] ?? null), href: drill?.(c.key, r) })),
  );
  const totals = hasTotals(effective.columns)
    ? totalsOf(effective.columns, effective.rows.map((r) => effective.columns.map((c) => r[c.key]))).map((t, i) => (t === null ? null : show(effective.columns[i].kind, t)))
    : null;
  const chart = effective.chart && effective.rows.length > 1 ? effective.chart : null;
  const chartCols = chart ? chart.series.map((k) => effective.columns.find((c) => c.key === k)).filter((c) => c !== undefined) : [];
  const chartRows = chart ? effective.rows.slice(0, 40) : [];
  const today = new Date();
  const kept = Object.fromEntries(filters.map((f) => [f.key, search[f.key]]));

  return (
    <div className="space-y-5">
      {/* For the Reports Center's Recently viewed and Last viewed (index-view.tsx). */}
      <RememberReport base={base.startsWith("/platform/reports/") ? "/platform/reports" : base.slice(0, base.lastIndexOf("/"))} reportKey={base.startsWith("/platform/reports/") ? `${mod}/${data.key}` : data.key} />

      {/* Top action strip: Customise button or Fixed report indicator */}
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <ReportCustomiseButton data={data} app={mod} base={base} savedReport={savedReport} />
        {savedReport && (
          <span className="text-xs text-ink-3">
            Base report:{" "}
            <Link href={base.split("?")[0]} className="font-medium text-ink underline hover:text-sage-deep">
              {data.title}
            </Link>
          </span>
        )}
      </div>

      {(data.dated || filters.length > 0) && (
        <section className="rounded-xl border border-rule bg-white px-5 py-4 print:hidden">
          {data.dated && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-meta font-medium text-ink-2">Period</span>
              {presets(today).map((p) => {
                const on = data.from === p.from && data.to === p.to;
                return (
                  <Link
                    key={p.label}
                    href={withQuery(base, { ...kept, from: p.from, to: p.to })}
                    aria-current={on ? "true" : undefined}
                    className={`rounded-full border px-3 py-1 text-meta ${on ? "border-ink bg-ink text-white" : "border-rule text-ink-2 hover:border-ink hover:text-ink"}`}
                  >
                    {p.label}
                  </Link>
                );
              })}
            </div>
          )}
          <form method="get" action={base} className="mt-3 flex flex-wrap items-end gap-4">
            {data.dated && (
              <>
                <label className="block">
                  <span className="mb-1 block text-meta font-medium text-ink-2">From</span>
                  <input
                    suppressHydrationWarning
                    type="date"
                    name="from"
                    defaultValue={search.from || data.from}
                    className="h-9 rounded-lg border border-rule bg-white px-2.5 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-meta font-medium text-ink-2">To</span>
                  <input
                    suppressHydrationWarning
                    type="date"
                    name="to"
                    defaultValue={search.to || data.to}
                    className="h-9 rounded-lg border border-rule bg-white px-2.5 text-sm"
                  />
                </label>
              </>
            )}
            {filters.map((f) => (
              <label key={f.key} className="block">
                <span className="mb-1 block text-meta font-medium text-ink-2">{f.label}</span>
                <select suppressHydrationWarning name={f.key} defaultValue={search[f.key] ?? ""} className="h-9 min-w-40 rounded-lg border border-rule bg-white px-2.5 text-sm">
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            {savedReport && <input type="hidden" name="saved" value={savedReport.id} />}
            <button suppressHydrationWarning type="submit" className="h-9 rounded-lg bg-ink px-4 text-sm font-medium text-white hover:bg-ink/90">
              Apply
            </button>
            {Object.values({ ...kept, from: search.from, to: search.to }).some(Boolean) && (
              <Link href={savedReport ? `${base}?saved=${savedReport.id}` : base} className="h-9 px-1 text-sm leading-9 text-ink-2 hover:text-ink hover:underline">
                Clear
              </Link>
            )}
          </form>
        </section>
      )}

      {effective.summary && effective.summary.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {effective.summary.map((f) => (
            <div key={f.label} className="rounded-xl border border-rule bg-white px-4 py-3">
              <p className="text-meta text-ink-3">{f.label}</p>
              <p className={`mt-1 text-xl font-semibold tabular-nums ${f.tone === "bad" ? "text-danger" : f.tone === "warn" ? "text-[#8a5a00]" : f.tone === "good" ? "text-sage-deep" : "text-ink"}`}>
                {f.value === null ? "—" : show(f.kind, f.value)}
              </p>
            </div>
          ))}
        </div>
      )}

      {chart && chartCols.length > 0 && (
        <section className="rounded-xl border border-rule bg-white px-5 py-4">
          <ReportChartView
            kind={chart.kind}
            labels={chartCols.map((c) => c.label)}
            points={chartRows.map((r) => ({
              x: show(effective.columns.find((c) => c.key === chart.x)?.kind ?? "text", r[chart.x] ?? null),
              values: chartCols.map((c) => (r[c.key] === null ? null : Number(r[c.key]))),
            }))}
            format={(v) => (chartCols[0].kind === "money" ? format.money(v) : chartCols[0].kind === "percent" ? `${Math.round(v * 100)}%` : format.count(v))}
          />
          {effective.rows.length > 40 && <p className="mt-1 text-meta text-ink-3">The chart shows the first 40 rows.</p>}
        </section>
      )}

      <section className="overflow-hidden rounded-xl border border-rule bg-white shadow-sm">
        {/* Zoho-style formal Report Header */}
        <div className="border-b border-rule bg-white px-6 py-4 text-center">
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-3">GetMeds Philippines Inc.</p>
          <h2 className="mt-0.5 text-lg font-bold text-ink">{effective.title}</h2>
          {data.dated && data.from && data.to && (
            <p className="mt-0.5 text-xs text-ink-2">
              From {format.date(data.from)} To {format.date(data.to)}
            </p>
          )}
        </div>

        {effective.rows.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="font-semibold text-ink">No data</p>
            <p className="mt-1 text-sm text-ink-3">Nothing matches this {data.dated ? "period" : "report"}{filters.some((f) => search[f.key]) ? " and these filters" : ""}. Try a wider period or clear the filters.</p>
          </div>
        ) : (
          <ReportTable title={effective.title} columns={effective.columns} rows={rows} totals={totals} canExport={canExport} />
        )}
      </section>

      {effective.notes && effective.notes.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-meta text-ink-3">
          {effective.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export { numeric };
