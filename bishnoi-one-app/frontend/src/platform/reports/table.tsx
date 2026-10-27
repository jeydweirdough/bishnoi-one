"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Download, Printer, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { Cell, ColumnKind } from "./types";

type Col = { key: string; label: string; kind: ColumnKind };

const numeric = (k: ColumnKind) => k === "money" || k === "number" || k === "percent";

/**
 * A report's rows: sort by any column (click its heading), search within them, totals at
 * the foot, a cell that leads to its record is a link. Exports what's shown (sorted and
 * searched) to CSV, which Excel opens, or prints it.
 */
export function ReportTable({ title, columns, rows, totals, canExport }: { title: string; columns: Col[]; rows: Cell[][]; totals: (string | null)[] | null; canExport: boolean }) {
  const [sort, setSort] = useState<{ i: number; dir: 1 | -1 } | null>(null);
  const [q, setQ] = useState("");
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    let list = t ? rows.filter((r) => r.some((c) => c.text.toLowerCase().includes(t))) : rows;
    if (sort) {
      const { i, dir } = sort;
      list = [...list].sort((a, b) => {
        const x = a[i].raw;
        const y = b[i].raw;
        if (x === null || x === "") return 1;
        if (y === null || y === "") return -1;
        return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })) * dir;
      });
    }
    return list;
  }, [rows, sort, q]);

  function exportCsv() {
    // A cell starting with = + - @ would be run as a formula by a spreadsheet.
    const safe = (s: string) => (/^[=+\-@]/.test(s) ? `'${s}` : s);
    const quote = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
    const lines = [columns.map((c) => quote(c.label)).join(","), ...shown.map((r) => r.map((c, i) => quote(safe(numeric(columns[i].kind) && typeof c.raw === "number" ? String(columns[i].kind === "money" ? c.raw / 100 : c.raw) : c.text))).join(","))];
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${title.replace(/[^\w-]+/g, "-").toLowerCase()}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // Dynamic totals calculated live over the shown/filtered rows (like Zoho Inventory)
  const dynamicTotals = useMemo(() => {
    if (!totals) return null;
    return columns.map((c, i) => {
      if (i === 0) return "Total";
      if (!numeric(c.kind)) return null;
      const sum = shown.reduce((acc, r) => acc + (typeof r[i]?.raw === "number" ? (r[i].raw as number) : 0), 0);
      if (c.kind === "money") {
        return `₱${(sum / 100).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }
      if (c.kind === "number") {
        return sum.toLocaleString("en-PH");
      }
      if (c.kind === "percent") {
        return `${Math.round(sum * 1000) / 10}%`;
      }
      return null;
    });
  }, [totals, shown, columns]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 print:hidden">
        <label className="relative block w-full max-w-xs">
          <span className="sr-only">Search the rows</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input suppressHydrationWarning type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the rows" className="h-9 w-full rounded-lg border border-rule bg-white pr-3 pl-9 text-sm outline-none focus:border-ink" />
        </label>
        <div className="flex items-center gap-2">
          <span className="text-meta text-ink-3">
            {shown.length === rows.length ? `${rows.length} row${rows.length === 1 ? "" : "s"}` : `${shown.length} of ${rows.length} rows`}
          </span>
          {canExport && (
            <button suppressHydrationWarning type="button" onClick={exportCsv} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-rule bg-white px-3 text-sm text-ink hover:border-ink">
              <Download className="size-4" aria-hidden /> Export to Excel (CSV)
            </button>
          )}
          <button suppressHydrationWarning type="button" onClick={() => window.print()} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-rule bg-white px-3 text-sm text-ink hover:border-ink">
            <Printer className="size-4" aria-hidden /> Print
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm" style={{ minWidth: `${Math.max(36, columns.length * 8)}rem` }}>
          <thead className="sticky top-0 bg-white">
            <tr className="border-y border-rule text-left text-meta text-ink-3">
              {columns.map((c, i) => {
                const on = sort?.i === i;
                return (
                  <th key={c.key} scope="col" aria-sort={on ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={`px-3 py-2.5 font-semibold first:pl-5 last:pr-5 ${numeric(c.kind) ? "text-right" : ""}`}>
                    <button
                      suppressHydrationWarning
                      type="button"
                      onClick={() => setSort(on ? (sort.dir === 1 ? { i, dir: -1 } : null) : { i, dir: numeric(c.kind) ? -1 : 1 })}
                      className={`inline-flex items-center gap-1 hover:text-ink ${on ? "text-ink" : ""}`}
                    >
                      {c.label}
                      {on ? sort.dir === 1 ? <ArrowUp className="size-3" aria-hidden /> : <ArrowDown className="size-3" aria-hidden /> : <ArrowUpDown className="size-3 opacity-40 print:hidden" aria-hidden />}
                    </button>
                  </th>
                );
              })}
            </tr>
            {/* Zoho-style prominent Total row at the top of the table */}
            {dynamicTotals && shown.length > 0 && (
              <tr className="border-b-2 border-rule-strong bg-bencher/40 font-semibold text-ink">
                {dynamicTotals.map((t, i) => (
                  <td key={columns[i].key} className={`px-3 py-2.5 first:pl-5 last:pr-5 font-bold ${numeric(columns[i].kind) ? "text-right tabular-nums text-ink" : "text-ink"}`}>
                    {t ?? (i === 0 ? "Total" : "")}
                  </td>
                ))}
              </tr>
            )}
          </thead>
          <tbody className="divide-y divide-rule">
            {shown.map((r, ri) => (
              <tr key={ri} className="hover:bg-bench/40">
                {r.map((c, i) => (
                  <td key={columns[i].key} className={`px-3 py-2 first:pl-5 last:pr-5 ${numeric(columns[i].kind) ? "text-right whitespace-nowrap tabular-nums" : ""} ${columns[i].kind === "datetime" ? "whitespace-nowrap text-meta text-ink-2" : ""}`}>
                    {c.text === "" ? <span className="text-ink-3">—</span> : c.href ? <Link href={c.href} className="text-ink underline decoration-rule-strong underline-offset-2 hover:decoration-ink">{c.text}</Link> : c.text}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {dynamicTotals && shown.length > 1 && (
            <tfoot>
              <tr className="border-t-2 border-rule-strong font-semibold bg-bencher/20">
                {dynamicTotals.map((t, i) => (
                  <td key={columns[i].key} className={`px-3 py-2.5 first:pl-5 last:pr-5 ${numeric(columns[i].kind) ? "text-right tabular-nums font-bold text-ink" : "font-bold text-ink"}`}>
                    {t ?? (i === 0 ? "Total" : "")}
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {/* Zoho-style Total Count & record summary footer */}
      <div className="flex items-center justify-between border-t border-rule bg-white px-5 py-3 text-meta text-ink-3">
        <span>Total Count: <strong className="font-semibold text-ink tabular-nums">{shown.length}</strong></span>
        <span>{shown.length === rows.length ? `All ${rows.length} records shown` : `Showing ${shown.length} of ${rows.length} records`}</span>
      </div>
    </div>
  );
}
