import type { ColumnKind, ReportColumn } from "./types";

// The Total row of every report (2026-10-28): only what adds up is added. Money and counts are summed;
// a percentage is never summed (26 people at 90% isn't 2,340%): it is the share of the totals it comes
// from (366 visited of 402 accounts: 91.0%), weighting each row by its size as the business reads it,
// or, when nothing says what it is a share of, the average of the rows. Days, rates, averages, prices
// and levels aren't added at all.

/** Counts that make sense to add up (not days, rates, averages, prices, levels…). */
export const adds = (label: string, kind: ColumnKind) =>
  kind === "money" || (kind === "number" && !/days|point|per day|cover|lead|rate|average|avg|age|level|price|cost per|score|percent|ratio|%/i.test(label));

type Raw = string | number | null | undefined;

const num = (v: Raw) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The two columns a percentage column is a share of: declared by the report, else found in the rows
 *  (a ÷ b gives the percentage on every row). */
function shareOf(columns: ReportColumn[], rows: Raw[][], p: number): [number, number] | null {
  const declared = columns[p].ratio;
  if (declared) {
    const a = columns.findIndex((c) => c.key === declared[0]);
    const b = columns.findIndex((c) => c.key === declared[1]);
    if (a >= 0 && b >= 0) return [a, b];
  }
  const counts = columns.map((c, i) => (adds(c.label, c.kind) ? i : -1)).filter((i) => i >= 0 && i !== p);
  const checked = rows.filter((r) => num(r[p]) !== null);
  if (checked.length === 0) return null;
  for (const b of counts) {
    for (const a of counts) {
      if (a === b) continue;
      const fits = checked.every((r) => {
        const pa = num(r[a]), pb = num(r[b]), pv = num(r[p]);
        if (pa === null || pb === null || pv === null) return false;
        if (pb === 0) return pa === 0;
        return Math.abs(pa / pb - pv) < 0.0006;  // within the rounding of a shown percentage
      });
      if (fits && checked.some((r) => (num(r[b]) ?? 0) > 0)) return [a, b];
    }
  }
  return null;
}

/** Each column's total over the rows given: a number, or null where a total means nothing. */
export function totalsOf(columns: ReportColumn[], rows: Raw[][]): (number | null)[] {
  const sums = columns.map((c, i) => (c.kind === "money" || c.kind === "number" ? rows.reduce((n, r) => n + (num(r[i]) ?? 0), 0) : 0));
  return columns.map((c, i) => {
    if (c.kind === "percent") {
      const pair = shareOf(columns, rows, i);
      if (pair) return sums[pair[1]] ? sums[pair[0]] / sums[pair[1]] : null;
      const values = rows.map((r) => num(r[i])).filter((v): v is number => v !== null);
      return values.length ? values.reduce((n, v) => n + v, 0) / values.length : null;
    }
    return adds(c.label, c.kind) ? sums[i] : null;
  });
}

/** Whether a report has a Total row worth showing. */
export const hasTotals = (columns: ReportColumn[]) => columns.some((c) => adds(c.label, c.kind));
