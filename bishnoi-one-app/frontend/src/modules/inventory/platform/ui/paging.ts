// Paging helpers with no React in them, so a server page can slice its rows
// and read ?page= itself; the Pager component (./pager.tsx) draws the controls.

/** How many rows a page holds, unless a list says otherwise. */
export const PAGE_SIZE = 25;

/** The page asked for in the address: 1 when it's missing or makes no sense. */
export function pageOf(value: string | string[] | undefined): number {
  const n = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(n) && n > 1 ? n : 1;
}

/** One page of rows already in hand, and the page actually shown (a page past the end shows the last). */
export function slicePage<T>(rows: T[], page: number, size = PAGE_SIZE): { rows: T[]; page: number } {
  const last = Math.max(1, Math.ceil(rows.length / size));
  const at = Math.min(Math.max(1, page), last);
  return { rows: rows.slice((at - 1) * size, at * size), page: at };
}

/** An address with `page` set (left out on the first page), keeping everything else in it. */
export function withPage(base: string, n: number): string {
  const [path, query = ""] = base.split("?");
  const params = new URLSearchParams(query);
  if (n > 1) params.set("page", String(n));
  else params.delete("page");
  return params.size ? `${path}?${params}` : path;
}
