"use client";

import { ChevronDown } from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { Fragment, useState, type ReactNode } from "react";
import { BulkList, type BulkSetup } from "../bulk/list";
import { SelectAllBox, SelectBox } from "../bulk/selection";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/src/components/ui/table";

export type Column = { key: string; label: string; align?: "left" | "right"; className?: string };

/** A row: its cells (drawn on the server), what opens under it, and the controls at its end. */
export type ExpandableRow = { id: string; cells: ReactNode[]; detail?: ReactNode; actions?: ReactNode; muted?: boolean; /** With `bulk`: its name, when it can be ticked. */ tick?: string };

/**
 * The list layout's table (src/platform/ui/list-layout.tsx), shadcn/ui's Table as Studio Admin lists its users:
 * muted headings, even rows,
 * and a row that opens in place to its details (an invoice's payments, an order's lines) with the
 * chevron at its end, so nobody leaves the list to look. One row open at a time keeps it tidy.
 */
export function ExpandableTable({ columns, rows, minWidth = "46rem", bulk }: { columns: Column[]; rows: ExpandableRow[]; minWidth?: string; bulk?: BulkSetup }) {
  const items = bulk ? rows.filter((r) => r.tick).map((r) => ({ id: r.id, name: r.tick! })) : [];
  if (bulk && items.length > 0) {
    return (
      <BulkList items={items} {...bulk}>
        <Rows columns={columns} rows={rows} minWidth={minWidth} ticks />
      </BulkList>
    );
  }
  return <Rows columns={columns} rows={rows} minWidth={minWidth} ticks={false} />;
}

function Rows({ columns, rows, minWidth, ticks }: { columns: Column[]; rows: ExpandableRow[]; minWidth: string; ticks: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  const span = columns.length + 1 + (ticks ? 1 : 0);
  return (
    <Table className="text-sm **:data-[slot='table-cell']:px-3 **:data-[slot='table-head']:px-3 [&_td:first-child]:pl-4 [&_th:first-child]:pl-4 [&_td:last-child]:pr-4 [&_th:last-child]:pr-4" style={{ minWidth }}>
      <TableHeader className="[&_tr]:border-t">
        <TableRow>
          {ticks && (
            <TableHead className="w-10">
              <SelectAllBox />
            </TableHead>
          )}
          {columns.map((c) => (
            <TableHead key={c.key} className={`py-3 font-normal text-muted-foreground ${c.align === "right" ? "text-right" : ""} ${c.className ?? ""}`}>
              {c.label}
            </TableHead>
          ))}
          <TableHead className="w-20">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const isOpen = open === r.id;
          return (
            <Fragment key={r.id}>
              <TableRow data-state={isOpen ? "selected" : undefined} className={`group ${r.muted ? "text-muted-foreground" : ""}`}>
                {ticks && <TableCell className="w-10 py-3">{r.tick && <SelectBox id={r.id} label={r.tick} />}</TableCell>}
                {r.cells.map((cell, i) => (
                  <TableCell key={columns[i].key} className={`py-3 whitespace-normal ${columns[i].align === "right" ? "text-right tabular-nums" : ""} ${columns[i].className ?? ""}`}>
                    {cell}
                  </TableCell>
                ))}
                <TableCell className="py-3">
                  <div className="flex items-center justify-end gap-1">
                    {r.actions}
                    {r.detail && (
                      <Button
                        suppressHydrationWarning
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => setOpen(isOpen ? null : r.id)}
                        aria-expanded={isOpen}
                        aria-label={isOpen ? "Close details" : "Open details"}
                        title={isOpen ? "Close details" : "Open details"}
                      >
                        <ChevronDown className={`transition-transform ${isOpen ? "rotate-180" : ""}`} aria-hidden />
                      </Button>
                    )}
                  </div>
                </TableCell>
              </TableRow>
              {isOpen && r.detail && (
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableCell colSpan={span} className="py-3 whitespace-normal">
                    <div className="animate-reshape">{r.detail}</div>
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          );
        })}
      </TableBody>
    </Table>
  );
}
