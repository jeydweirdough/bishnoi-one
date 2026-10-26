// The report contract every module's API answers (decided 2026-10-24, benchmarks/surpass.md §11):
// GET /<module>/reports lists them; GET /<module>/reports/<key> runs one. One screen kit draws
// any of them (src/platform/reports/), so every module's reports read and work the same.

/** text, number, money, date, datetime, percent (a fraction: 0.25 is 25%). */
export type ColumnKind = "text" | "number" | "money" | "date" | "datetime" | "percent";

export type ReportColumn = { key: string; label: string; kind: ColumnKind };

/** A choice the report can be narrowed by (warehouse, team, status). */
export type ReportFilter = { key: string; label: string; options: { value: string; label: string }[] };

/** A headline figure over the rows, beside the table. */
export type ReportFigure = { label: string; value: number | null; kind: ColumnKind; tone?: "good" | "warn" | "bad" };

/** How to chart it: `x` a column, `series` the number columns drawn against it. */
export type ReportChart = { kind: "bar" | "line"; x: string; series: string[] };

export type ReportInfo = { key: string; title: string; group: string; about: string; dated?: boolean; fixed?: boolean };

export type ReportData = ReportInfo & {
  from?: string;
  to?: string;
  filters?: ReportFilter[];
  columns: ReportColumn[];
  rows: Record<string, string | number | null>[];
  summary?: ReportFigure[];
  chart?: ReportChart | null;
  notes?: string[];
};

/** A cell as the screen shows it: drawn on the server in the module's own formats, sorted by `raw`. */
export type Cell = { raw: string | number | null; text: string; href?: string };
