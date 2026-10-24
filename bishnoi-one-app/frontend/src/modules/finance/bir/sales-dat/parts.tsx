import type { ReactNode } from "react";

// Small pieces the Sales DAT screen's three parts share.

/** A section folded away until opened, with a short note beside its title. */
export function Fold({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <details className="rounded-[3px] bg-sheet shadow-sheet">
      <summary className="cursor-pointer px-5 py-3 text-sm font-semibold">
        {title}
        {note && <span className="font-normal text-ink-3"> · {note}</span>}
      </summary>
      <div className="border-t border-rule">{children}</div>
    </details>
  );
}

/** A plain table that scrolls when long; `numeric` columns are right-aligned figures. */
export function Table({ head, rows, numeric = [] }: { head: string[]; rows: ReactNode[][]; numeric?: number[] }) {
  return (
    <div className="max-h-[28rem] overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-sheet">
          <tr className="text-left text-meta text-ink-3">
            {head.map((h, i) => (
              <th key={h} className={`px-5 py-1 font-medium ${numeric.includes(i) ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-rule align-top">
              {r.map((c, j) => (
                <td key={j} className={`px-5 py-1.5 ${numeric.includes(j) ? "text-right font-mono tabular-nums" : ""}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** "1 item", "3 items". */
export const pl = (n: number, one: string, many = one + "s") => `${n} ${n === 1 ? one : many}`;
