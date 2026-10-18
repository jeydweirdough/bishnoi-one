import type { BatchRow, Reference } from "./types";

// The reference lists as GraphQL fields: a page asks for the lists its form
// picks from and nothing else (every product with its prices is the heaviest).
const LISTS = {
  categories: "categories { id name path parentId isActive }",
  brands: "brands { id name isActive }",
  units: "units { code name isActive }",
  suppliers: "suppliers { id code name isActive }",
  warehouses: "warehouses { id code name isActive locations { id code name isDefault isActive } }",
  products: "products { id sku name unit trackBatches trackExpiry trackSerials status costPrice sellingPrice supplierId }",
} satisfies Record<keyof Reference, string>;

/** `reference { ... }` with only these lists, for a page's query. */
export function referenceOf(...lists: (keyof Reference)[]): string {
  return `reference { ${lists.map((l) => LISTS[l]).join(" ")} }`;
}

/** The batches a line could be picked from, soonest to expire first, out of a warehouse's batches. */
export function batchChoices(rows: BatchRow[], productId: string, day: (iso: string) => string) {
  return rows.filter((b) => b.product.id === productId).map((b) => ({ id: b.id, label: `${b.batchNo}${b.expiresOn ? `, expires ${day(b.expiresOn)}` : ""} (${b.onHand})` }));
}

/** A page's filters as query variables: the ones left blank are left out, as REST's `query()` does. */
export function given(values: Record<string, string | number | boolean | null | undefined>): Record<string, string | number | boolean> {
  return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== "" && v !== null && v !== undefined && v !== false)) as Record<string, string | number | boolean>;
}
