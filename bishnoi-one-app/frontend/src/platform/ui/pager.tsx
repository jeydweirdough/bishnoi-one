"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { PAGE_SIZE, slicePage, withPage } from "./paging";

// Every table's pages, one way: "26–50 of 132", the page numbers, and the
// previous and next pages. A list the server pages (or slices) moves by its
// address, so a page can be shared or come back to; a list held in the browser
// moves in place. The same look either way.

/** The page numbers to offer: the first, the last, and two either side of this one; gaps between. */
function numbers(page: number, last: number): (number | "gap")[] {
  const out: (number | "gap")[] = [];
  for (let n = 1; n <= last; n++) {
    if (n === 1 || n === last || Math.abs(n - page) <= 1 || (page <= 3 && n <= 4) || (page >= last - 2 && n >= last - 3)) out.push(n);
    else if (out.at(-1) !== "gap") out.push("gap");
  }
  return out;
}

const CELL = "inline-flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-meta tabular-nums transition-colors";

/**
 * The way through a table's pages. `base` for a list paged by its address (the
 * list's own address, filters and all: a server page can pass it as it is),
 * `onPage` for one held in the browser. Nothing at all while there are no rows;
 * only the count while they fit on one page.
 */
export function Pager({ total, page, size = PAGE_SIZE, base, onPage, noun }: { total: number; page: number; size?: number; base?: string; onPage?: (n: number) => void; noun?: string }) {
  if (total <= 0) return null;
  const last = Math.max(1, Math.ceil(total / size));
  const from = (page - 1) * size + 1;
  const to = Math.min(total, page * size);
  const go = (n: number, label: ReactNode, aria: string, current = false) => {
    const className = `${CELL} ${current ? "bg-ink font-semibold text-white" : "text-ink-2 hover:bg-sheet hover:text-ink"}`;
    if (base !== undefined) {
      return (
        <Link key={aria} href={withPage(base, n)} scroll={false} aria-label={aria} aria-current={current ? "page" : undefined} className={className}>
          {label}
        </Link>
      );
    }
    return (
      <button suppressHydrationWarning key={aria} type="button" onClick={() => onPage?.(n)} aria-label={aria} aria-current={current ? "page" : undefined} className={className}>
        {label}
      </button>
    );
  };
  const off = (label: ReactNode, aria: string) => (
    <span key={aria} aria-hidden className={`${CELL} text-ink-3/50`}>
      {label}
    </span>
  );
  return (
    <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3 text-meta text-ink-3">
      <span className="tabular-nums">
        {last > 1 ? `${from}–${to} of ${total}` : `All ${total}`}
        {noun ? ` ${noun}` : ""}
      </span>
      {last > 1 && (
        <span className="flex flex-wrap items-center gap-1">
          {page > 1 ? go(page - 1, <ChevronLeft className="size-4" aria-hidden />, "Previous page") : off(<ChevronLeft className="size-4" />, "Previous page")}
          {numbers(page, last).map((n, i) =>
            n === "gap" ? (
              <span key={`gap${i}`} className="px-1 text-ink-3" aria-hidden>
                …
              </span>
            ) : (
              go(n, n, `Page ${n}`, n === page)
            ),
          )}
          {page < last ? go(page + 1, <ChevronRight className="size-4" aria-hidden />, "Next page") : off(<ChevronRight className="size-4" />, "Next page")}
        </span>
      )}
    </nav>
  );
}

/**
 * Pages for rows held in the browser. `key`: what the rows were picked by (a
 * search, a filter); when it changes the list starts again at the first page.
 * Rows added or taken away keep the page, or the last one there is.
 */
export function usePages<T>(all: T[], { size = PAGE_SIZE, key = "" }: { size?: number; key?: string } = {}) {
  const [at, setAt] = useState<{ key: string; page: number }>({ key, page: 1 });
  const { rows, page } = slicePage(all, at.key === key ? at.page : 1, size);
  return { rows, pager: { total: all.length, page, size, onPage: (n: number) => setAt({ key, page: n }) } };
}
