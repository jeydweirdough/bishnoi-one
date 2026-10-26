import type { ColumnKind, ReportColumn, ReportData } from "./types";

// A report someone built from one of a module's reports (decided 2026-10-26, version 1 of the
// report builder). Only the choices are kept (on the Platform, app/routers/saved_reports.py); the
// module's report runs with the viewer's own access and this applies them, so nobody sees more
// than they may. Fixed reports (the accounting statements) are never customised.

export type FilterOp = "is" | "is_not" | "contains" | "gt" | "lt" | "empty" | "not_empty";
export type Measure = "sum" | "count" | "avg" | "min" | "max";

export type Definition = {
  /** The columns shown, in order; all when empty. */
  columns?: string[];
  /** Rows kept: every condition must hold. */
  filters?: { column: string; op: FilterOp; value?: string }[];
  /** One column to group by: a row per value, with a count and each number column totalled. */
  groupBy?: string | null;
  /** How each number column is totalled when grouped (sum unless said). */
  measures?: Record<string, Measure>;
  /** Sorting: the first one first. */
  sort?: { column: string; desc?: boolean }[];
  /** The chart: none, or bars or a line over the first column. */
  chart?: "none" | "bar" | "line";
};

export type SavedReport = { id: string; app: string; baseKey: string; name: string; definition: Definition; shared: boolean; mine: boolean; owner: string; updatedAt: string | null };

export const OPS: { value: FilterOp; label: string; needs: boolean; kinds?: ColumnKind[] }[] = [
  { value: "is", label: "is", needs: true },
  { value: "is_not", label: "is not", needs: true },
  { value: "contains", label: "contains", needs: true, kinds: ["text"] },
  { value: "gt", label: "is more than", needs: true, kinds: ["number", "money", "percent", "date", "datetime"] },
  { value: "lt", label: "is less than", needs: true, kinds: ["number", "money", "percent", "date", "datetime"] },
  { value: "empty", label: "is empty", needs: false },
  { value: "not_empty", label: "is not empty", needs: false },
];

export const MEASURES: { value: Measure; label: string }[] = [
  { value: "sum", label: "Total" },
  { value: "avg", label: "Average" },
  { value: "min", label: "Lowest" },
  { value: "max", label: "Highest" },
  { value: "count", label: "Count" },
];

const NUMERIC: ColumnKind[] = ["number", "money", "percent"];
export const isNumeric = (c: ReportColumn) => NUMERIC.includes(c.kind);

type Row = ReportData["rows"][number];
type Value = Row[string];

/** A typed value as the filter compares it: money is typed in pesos, kept in centavos. */
function typed(c: ReportColumn, raw: string): number | string {
  if (c.kind === "money") return Math.round(Number(raw.replace(/[^\d.-]/g, "")) * 100);
  if (c.kind === "percent") return Number(raw.replace(/[^\d.-]/g, "")) / 100;
  if (c.kind === "number") return Number(raw.replace(/[^\d.-]/g, ""));
  return raw.trim().toLowerCase();
}

function holds(row: Row, c: ReportColumn, op: FilterOp, raw = ""): boolean {
  const v = row[c.key];
  const blank = v === null || v === undefined || v === "";
  if (op === "empty") return blank;
  if (op === "not_empty") return !blank;
  if (blank) return op === "is_not";
  const want = typed(c, raw);
  const have: number | string = typeof v === "number" ? v : String(v).toLowerCase();
  if (op === "contains") return String(have).includes(String(want));
  if (op === "is") return typeof want === "number" ? Number(have) === want : String(have) === want;
  if (op === "is_not") return typeof want === "number" ? Number(have) !== want : String(have) !== want;
  if (op === "gt") return typeof want === "number" ? Number(have) > want : String(have) > want;
  if (op === "lt") return typeof want === "number" ? Number(have) < want : String(have) < want;
  return true;
}

function measure(values: Value[], how: Measure): number | null {
  const nums = values.filter((v): v is number => typeof v === "number");
  if (how === "count") return values.filter((v) => v !== null && v !== "").length;
  if (!nums.length) return null;
  if (how === "sum") return nums.reduce((a, b) => a + b, 0);
  if (how === "avg") return Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 1000) / 1000;
  if (how === "min") return Math.min(...nums);
  return Math.max(...nums);
}

function compare(a: Value, b: Value): number {
  if (a === b) return 0;
  if (a === null || a === undefined || a === "") return 1;
  if (b === null || b === undefined || b === "") return -1;
  return typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b));
}

/** The module's report, with the saved choices applied. */
export function applyDefinition(base: ReportData, def: Definition, name?: string): ReportData {
  const byKey = new Map(base.columns.map((c) => [c.key, c]));
  let rows = base.rows.filter((r) => (def.filters ?? []).every((f) => !byKey.has(f.column) || holds(r, byKey.get(f.column)!, f.op, f.value)));
  let columns = (def.columns?.length ? def.columns : base.columns.map((c) => c.key)).map((k) => byKey.get(k)).filter((c): c is ReportColumn => Boolean(c));

  const group = def.groupBy ? byKey.get(def.groupBy) : undefined;
  if (group) {
    const numeric = columns.filter((c) => isNumeric(c) && c.key !== group.key);
    const buckets = new Map<string, Row[]>();
    for (const r of rows) {
      const k = r[group.key] === null || r[group.key] === undefined || r[group.key] === "" ? "(none)" : String(r[group.key]);
      buckets.set(k, [...(buckets.get(k) ?? []), r]);
    }
    rows = [...buckets.entries()].map(([k, rs]) => {
      const out: Row = { [group.key]: k, __count: rs.length };
      for (const c of numeric) out[c.key] = measure(rs.map((r) => r[c.key]), def.measures?.[c.key] ?? "sum");
      return out;
    });
    const label = (c: ReportColumn) => {
      const how = def.measures?.[c.key] ?? "sum";
      return how === "sum" ? c.label : `${MEASURES.find((m) => m.value === how)!.label} ${c.label.toLowerCase()}`;
    };
    columns = [group, { key: "__count", label: "Rows", kind: "number" }, ...numeric.map((c) => ({ ...c, label: label(c), kind: (def.measures?.[c.key] === "count" ? "number" : c.kind) as ColumnKind }))];
  }

  for (const s of [...(def.sort ?? [])].reverse()) rows = [...rows].sort((a, b) => compare(a[s.column], b[s.column]) * (s.desc ? -1 : 1));

  // Headline figures: how many, and the first two money columns totalled.
  const money = columns.filter((c) => c.kind === "money").slice(0, 2);
  const summary = [
    { label: group ? `${group.label}s` : "Rows", value: rows.length, kind: "number" as const },
    ...money.map((c) => ({ label: c.label, value: rows.reduce((t, r) => t + (typeof r[c.key] === "number" ? (r[c.key] as number) : 0), 0), kind: "money" as const })),
  ];
  const firstNumber = columns.find((c) => isNumeric(c) && c.key !== "__count") ?? columns.find((c) => c.key === "__count");
  const chart = def.chart && def.chart !== "none" && firstNumber && columns[0] && columns[0].key !== firstNumber.key ? { kind: def.chart, x: columns[0].key, series: [firstNumber.key] } : null;

  return { ...base, title: name ?? base.title, columns, rows, summary, chart };
}
