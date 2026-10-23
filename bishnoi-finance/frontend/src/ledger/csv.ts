// Reading a chart of accounts from a CSV, in the browser (nothing of the file is uploaded or
// kept: only its rows go to the API to be checked). Oojeema's columns (Code, Name, Class,
// Nature, Type, Parent, FS Presentation) and Zoho's (Account Code, Account Name, Account
// Type, Parent Account, Description) are both recognised by their headings. Plain, with no
// imports, so tests/chart-csv.test.mjs runs it as it is.

/** Rows of cells: commas (or semicolons, or tabs: whichever the heading line uses), quotes
 *  around cells that hold them, "" for a quote inside one, and Windows or Unix line ends. */
export function parseCsv(text: string): string[][] {
  const body = text.replace(/^﻿/, "");
  const first = body.slice(0, body.search(/\r?\n|$/));
  const sep = [",", ";", "\t"].sort((a, b) => first.split(b).length - first.split(a).length)[0];
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (quoted) {
      if (c === '"' && body[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === sep) {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && body[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += c;
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows.filter((r) => r.some((x) => x.trim()));
}

export type ChartRow = { code: string | null; name: string | null; kind: string | null; nature: string | null; statement: string | null; parent: string | null; description: string | null };

// Each field, and the headings that hold it (lower case).
const HEADINGS: Record<keyof ChartRow, string[]> = {
  code: ["code", "account code"],
  name: ["name", "account name"],
  kind: ["class", "account type", "account class"],
  nature: ["nature", "normal balance"],
  statement: ["fs presentation", "financial statement", "statement"],
  parent: ["parent", "parent account", "parent account name"],
  description: ["description"],
};

/** The chart's rows by heading; null when the file has no code and name columns. */
export function chartRows(text: string): ChartRow[] | null {
  const [head, ...rest] = parseCsv(text);
  if (!head) return null;
  const names = head.map((h) => h.trim().toLowerCase());
  const at = Object.fromEntries(Object.entries(HEADINGS).map(([field, options]) => [field, names.findIndex((n) => options.includes(n))])) as Record<keyof ChartRow, number>;
  if (at.code < 0 || at.name < 0) return null;
  const get = (r: string[], i: number) => (i >= 0 ? (r[i] ?? "").trim() || null : null);
  return rest.map((r) => ({
    code: get(r, at.code),
    name: get(r, at.name),
    kind: get(r, at.kind),
    nature: get(r, at.nature),
    statement: get(r, at.statement),
    parent: get(r, at.parent),
    description: get(r, at.description),
  }));
}
