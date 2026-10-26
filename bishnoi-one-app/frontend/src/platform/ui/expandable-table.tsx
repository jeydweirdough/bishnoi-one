"use client";

import { ChevronDown } from "lucide-react";
import { Fragment, useState, type ReactNode } from "react";

export type Column = { key: string; label: string; align?: "left" | "right"; className?: string };

/** A row: its cells (drawn on the server), what opens under it, and the controls at its end. */
export type ExpandableRow = { id: string; cells: ReactNode[]; detail?: ReactNode; actions?: ReactNode; muted?: boolean };

/**
 * The list layout's table (src/platform/ui/list-layout.tsx): small uppercase headings, even rows,
 * and a row that opens in place to its details (an invoice's payments, an order's lines) with the
 * chevron at its end, so nobody leaves the list to look. One row open at a time keeps it tidy.
 */
export function ExpandableTable({ columns, rows, minWidth = "46rem" }: { columns: Column[]; rows: ExpandableRow[]; minWidth?: string }) {
  const [open, setOpen] = useState<string | null>(null);
  const span = columns.length + 1;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={{ minWidth }}>
        <thead>
          <tr className="border-b border-rule text-left text-[0.6875rem] font-semibold tracking-[0.06em] text-ink-3 uppercase">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`px-3 py-3 font-semibold first:pl-5 ${c.align === "right" ? "text-right" : ""} ${c.className ?? ""}`}>
                {c.label}
              </th>
            ))}
            <th scope="col" className="w-20 pr-5">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isOpen = open === r.id;
            return (
              <Fragment key={r.id}>
                <tr className={`border-b border-rule transition-colors ${isOpen ? "bg-mint/60" : "hover:bg-bench/60"} ${r.muted ? "text-ink-3" : ""}`}>
                  {r.cells.map((cell, i) => (
                    <td key={columns[i].key} className={`px-3 py-3 first:pl-5 ${columns[i].align === "right" ? "text-right tabular-nums" : ""} ${columns[i].className ?? ""}`}>
                      {cell}
                    </td>
                  ))}
                  <td className="py-3 pr-5">
                    <div className="flex items-center justify-end gap-1">
                      {r.actions}
                      {r.detail && (
                        <button
                          suppressHydrationWarning
                          type="button"
                          onClick={() => setOpen(isOpen ? null : r.id)}
                          aria-expanded={isOpen}
                          aria-label={isOpen ? "Close details" : "Open details"}
                          title={isOpen ? "Close details" : "Open details"}
                          className="grid size-8 place-items-center rounded-lg text-ink-3 hover:bg-mint-2 hover:text-sage-deep"
                        >
                          <ChevronDown className={`size-4 transition-transform ${isOpen ? "rotate-180 text-sage-deep" : ""}`} aria-hidden />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {isOpen && r.detail && (
                  <tr className="border-b border-rule bg-mint/40">
                    <td colSpan={span} className="px-5 py-3">
                      <div className="animate-reshape">{r.detail}</div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
