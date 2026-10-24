import "server-only";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import type { IconName } from "@/src/modules/inventory/platform/ui/icons";

// The order Inventory is set up in, as the CRM guides its own: what has to
// exist before the next thing can be made. A warehouse to keep stock in, and
// suppliers to buy from; then products, priced; then stock received into them.
// Moving stock (transfers, orders) needs stock. Each New page checks what it
// needs first and, if something's missing, offers to make that and come back.

export type Setup = { warehouses: number; suppliers: number; products: number; unpriced: number; stocked: number; receipts: number };

export type Need = "warehouse" | "twoWarehouses" | "supplier" | "product" | "stock";

export type Step = {
  key: string;
  title: string;
  why: string;
  icon: IconName;
  href: string;
  action: string;
  /** Who may do it. */
  permission: string;
  done: (s: Setup) => boolean;
  /** What has to be done before this step can be. */
  after?: string[];
  optional?: boolean;
};

export const STEPS: Step[] = [
  { key: "warehouse", title: "Add a warehouse", why: "Where stock is kept. Every receipt, transfer and order belongs to one.", icon: "warehouses", href: "/inventory/warehouses?add=1", action: "Add warehouse", permission: "warehouses.manage", done: (s) => s.warehouses > 0 },
  { key: "supplier", title: "Add suppliers", why: "Vendors you buy from, referenced on purchase orders and receipts.", icon: "suppliers", href: "/inventory/suppliers/new", action: "Add supplier", permission: "suppliers.create", done: (s) => s.suppliers > 0, optional: true },
  { key: "product", title: "Add products", why: "Items you stock, with their unit, batch and expiry tracking, and reorder levels.", icon: "products", href: "/inventory/products/new", action: "Add product", permission: "products.create", done: (s) => s.products > 0 },
  { key: "prices", title: "Set product prices", why: "Products without a cost have no stock value, and products without a selling price are sold at zero.", icon: "money", href: "/inventory/products", action: "View products", permission: "products.edit", done: (s) => s.products > 0 && s.unpriced === 0, after: ["product"] },
  { key: "stock", title: "Receive first stock", why: "Stock is received through a goods receipt, with or without a purchase order.", icon: "receiving", href: "/inventory/receipts/new", action: "Receive stock", permission: "receiving.receive", done: (s) => s.receipts > 0, after: ["warehouse", "product"] },
];

/** What each need means, and the step that meets it. */
const NEEDS: Record<Need, { met: (s: Setup) => boolean; says: string; step: string; action?: string }> = {
  warehouse: { met: (s) => s.warehouses > 0, says: "a warehouse to keep the stock in", step: "warehouse" },
  twoWarehouses: { met: (s) => s.warehouses > 1, says: "a second warehouse to move stock to", step: "warehouse", action: "Add another warehouse" },
  supplier: { met: (s) => s.suppliers > 0, says: "a supplier to buy from", step: "supplier" },
  product: { met: (s) => s.products > 0, says: "a product to put on it", step: "product" },
  stock: { met: (s) => s.stocked > 0, says: "stock on hand to move", step: "stock" },
};

export async function loadSetup(): Promise<Setup> {
  const { setup } = await loadQuery<{ setup: Setup }>("query Setup { setup }", {}, ["setup"]);
  return setup;
}

/** What's missing for a page, in the order to do it, each with where to go and come back. */
export function missingFor(setup: Setup, needs: Need[], then: string) {
  return needs
    .filter((n) => !NEEDS[n].met(setup))
    .map((n) => {
      const step = STEPS.find((s) => s.key === NEEDS[n].step)!;
      const join = step.href.includes("?") ? "&" : "?";
      return { need: n, says: NEEDS[n].says, step, action: NEEDS[n].action ?? step.action, href: `${step.href}${join}then=${encodeURIComponent(then)}` };
    });
}

/** Whether a step is waiting on another one first. */
export function blockedBy(step: Step, setup: Setup): Step | undefined {
  return (step.after ?? []).map((k) => STEPS.find((s) => s.key === k)!).find((s) => !s.done(setup));
}
