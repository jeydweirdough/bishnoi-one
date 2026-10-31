// CSV for every module (2026-10-30): reading a file in the browser (nothing of it is uploaded or kept)
// and writing one to download. The same reader as Finance's chart import (src/modules/finance/ledger/csv.ts,
// kept import-free there for its own test).

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

/** A CSV file's text from rows: cells with commas, quotes or line ends quoted; a BOM so Excel reads UTF-8. */
export function toCsv(rows: (string | number | boolean | null | undefined)[][]): string {
  const cell = (v: string | number | boolean | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return "﻿" + rows.map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}
