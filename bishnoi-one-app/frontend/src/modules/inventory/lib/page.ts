import "server-only";
import { redirect } from "next/navigation";
import { getCompanyMe } from "@/src/modules/inventory/platform/lib/api";
import { makeFormat } from "@/src/modules/inventory/platform/lib/format";
import { PAGE_SIZE, pageOf, withPage } from "@/src/modules/inventory/platform/ui/paging";

export type Search = Promise<Record<string, string | string[] | undefined>>;
export type Params<T> = Promise<T>;

/** Who's asking, what they may do, and how their company writes money and dates. */
export async function context() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const may = (permission: string) => me.permissions?.includes(permission) ?? false;
  /** A moment as the company's clocks show it: "24 Sep 2026, 9:42 AM". */
  const stamp = fmt.on({ dateStyle: "medium", timeStyle: "short" });
  return { me, fmt, may, at: (iso: string | null) => (iso ? stamp.format(new Date(iso)) : "—"), day: (key: string | null) => (key ? fmt.dateLabel(key) : "—") };
}

/** What this person may add from inside a form ("+ New …"), by their role. */
export function canAddFrom(may: (permission: string) => boolean) {
  const catalog = may("products.create");
  return {
    category: catalog,
    brand: catalog,
    unit: catalog,
    product: catalog,
    supplier: may("suppliers.create"),
    warehouse: may("warehouses.manage"),
    location: may("warehouses.manage"),
  };
}

/**
 * The page of a list asked for in the address (?page=), and what to ask the
 * API for: `limit` and `offset`, so the database cuts the page.
 */
export function paging(search: Record<string, string | string[] | undefined>, size = PAGE_SIZE) {
  const page = pageOf(search.page);
  return { page, size, vars: { limit: size, offset: (page - 1) * size } };
}

/** A page past the end (rows removed since, or a typed address) goes to the last page there is. */
export function keepInRange(rows: number, total: number, page: number, base: string, size = PAGE_SIZE) {
  if (rows === 0 && total > 0 && page > 1) redirect(withPage(base, Math.ceil(total / size)));
}
