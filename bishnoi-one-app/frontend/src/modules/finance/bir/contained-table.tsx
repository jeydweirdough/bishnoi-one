"use client";

import { Children, Fragment, useState, type ReactNode } from "react";
import { Pager, usePages } from "@/src/platform/ui/pager";

/** Page record groups together; printing always includes the entire report. */
export function ContainedTable({ head, children, foot, wide = "min-w-[48rem]", grouped = false }: {
  head: { label: string; right?: boolean }[]; children: ReactNode; foot?: ReactNode; wide?: string; grouped?: boolean;
}) {
  const all: ReactNode[] = grouped && Array.isArray(children)
    ? children.map((group, i) => <Fragment key={Children.toArray(group).map(row => typeof row === "object" && row && "key" in row ? row.key : i).join("|")}>{group}</Fragment>)
    : Children.toArray(children);
  const [size, setSize] = useState(25);
  const key = all.map(row => typeof row === "object" && row && "key" in row ? row.key : "").join("|");
  const { rows, pager } = usePages(all, { size, key });
  const table = (body: ReactNode) => <table className={`w-full ${wide} text-sm print:min-w-0`}>
    <thead className="sticky top-0 z-[1] bg-sheet print:static"><tr className="border-b border-rule text-left text-caps text-ink-3">
      {head.map(h => <th scope="col" key={h.label} className={`px-3 py-2.5 font-semibold first:pl-5 last:pr-5 ${h.right ? "text-right" : ""}`}>{h.label}</th>)}
    </tr></thead>
    <tbody className="divide-y divide-rule">{body}</tbody>
    {foot && <tfoot>{foot}</tfoot>}
  </table>;
  return <section className="min-w-0 max-w-full rounded-xl border border-rule bg-sheet shadow-sheet">
    <div className="print:hidden">
      {all.length > 10 && <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-4 py-2">
        <label className="flex items-center gap-2 text-meta text-ink-2">{grouped ? "Entries" : "Rows"} per page
          <select aria-label={grouped ? "Entries per page" : "Rows per page"} value={size} onChange={e => setSize(Number(e.target.value))} className="h-8 rounded-lg border border-rule-strong bg-sheet px-2">
            {[10,25,50,100].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        {foot && <span className="text-meta text-ink-3">Totals cover the full report</span>}
      </div>}
      <div key={`${pager.page}:${size}`} role="region" aria-label={`${head[0]?.label ?? "Report"} table`} tabIndex={0} className="max-h-[60vh] max-w-full overflow-auto overscroll-contain focus-visible:outline-2 focus-visible:outline-hema">
        {table(rows)}
      </div>
      {all.length > 10 && <div className="border-t border-rule px-4 pb-3"><Pager {...pager} noun={grouped ? "entries" : "rows"} /></div>}
    </div>
    <div className="hidden print:block">{table(all)}</div>
  </section>;
}
