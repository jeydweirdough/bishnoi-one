"use client";

import type { ReactNode } from "react";
import { Sidebar, type Process, type Step } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/modules/inventory/platform/ui/icons";
import type { Me } from "@/src/modules/inventory/platform/lib/types";

// Inventory's menu as Zoho Inventory lays it out (decided 2026-10-24, benchmarks/surpass.md §1):
// Items, Inventory, Sales, Purchases, Reports, in Zoho's page names; users and roles at the foot. The sidebar itself is
// src/platform/shell/sidebar.tsx, the same for every module.

/** How many things wait, by alert key (Inventory's /inventory/alerts), for the counts on the steps. */
export type Waiting = Record<string, number>;

/** How many things aren't set up yet, by kind (/inventory/unset). */
export type Unset = Record<string, number>;

type Item = Step & { sees: string[]; waits?: string[] };

function menu(me: Me, waiting: Waiting, unset: Unset): { home: Step | null; processes: Process[]; foot: Process[] } {
  const may = (p: string) => me.permissions?.includes(p) ?? false;
  const count = (keys: string[] = []) => keys.reduce((n, k) => n + (waiting[k] ?? 0), 0) || undefined;
  const keep = (items: Item[]): Step[] => items.filter((i) => i.sees.some(may)).map(({ sees: _s, waits, ...step }) => ({ ...step, count: count(waits) }));
  // As the CRM lays its menu out (decided 2026-10-26): the work in the order it happens (items,
  // stock, selling, buying), Reports as one row, then Users and roles and Settings at the foot.
  // The lists that only set things up (warehouses, categories, brands, units) are Settings.
  const processes: Process[] = [
    {
      label: "Items",
      icon: "products",
      steps: keep([
        { href: "/inventory/products", label: "Items", icon: "products", exact: true, sees: ["products.view"], missing: unset.productPrices ? { count: unset.productPrices, says: `${unset.productPrices} ${unset.productPrices === 1 ? "item has" : "items have"} no selling price or cost` } : undefined },
        // The FDA registrations, many at once (app/cpr.py).
        { href: "/inventory/products/cpr", label: "Item registrations (CPR)", icon: "info", sees: ["products.edit"] },
      ]),
    },
    {
      label: "Inventory",
      icon: "stock",
      steps: keep([
        { href: "/inventory/stock", label: "Stock on hand", icon: "stock", sees: ["stock.view"] },
        { href: "/inventory/batches", label: "Batches", icon: "batches", sees: ["stock.view"] },
        { href: "/inventory/serials", label: "Serial numbers", icon: "serials", sees: ["stock.view"] },
        { href: "/inventory/transfers", label: "Transfer orders", icon: "transfers", sees: ["transfers.view"] },
        { href: "/inventory/adjustments", label: "Inventory adjustments", icon: "adjustments", sees: ["adjustments.view"] },
        { href: "/inventory/counts", label: "Inventory counts", icon: "counts", sees: ["counts.view"] },
      ]),
    },
    {
      label: "Sales",
      icon: "issuance",
      steps: keep([
        { href: "/inventory/orders", label: "Sales orders", icon: "issuance", sees: ["orders.view"] },
        { href: "/inventory/reservations", label: "Reservations", icon: "reservations", sees: ["orders.view"] },
      ]),
    },
    // Buying, in order: the vendor, the purchase order, then the goods received.
    {
      label: "Purchases",
      icon: "purchaseOrders",
      flow: true,
      steps: keep([
        { href: "/inventory/suppliers", label: "Vendors", icon: "suppliers", sees: ["suppliers.view"] },
        { href: "/inventory/purchase-orders", label: "Purchase orders", icon: "purchaseOrders", also: ["/inventory/backorders"], sees: ["purchasing.view"] },
        { href: "/inventory/receipts", label: "Purchase receives", icon: "receiving", sees: ["receiving.view"] },
      ]),
    },
    // Reports, and the stock movements behind them (what came in and went out, when).
    {
      label: "Reports",
      icon: "report",
      steps: keep([
        { href: "/inventory/reports", label: "Reports", icon: "report", exact: true, also: ["/inventory/reports", "/inventory/alerts"], sees: ["reports.view"] },
        { href: "/inventory/movements", label: "Stock movements", icon: "history", sees: ["stock.view"] },
      ]),
    },
  ];
  const foot: Process[] = [
    {
      label: "Users and roles",
      icon: "people",
      steps: keep([
        { href: "/inventory/admin/users", label: "Users", icon: "people", sees: ["admin.users"] },
        { href: "/platform/roles", label: "Roles", icon: "roles", sees: ["admin.roles"] },
      ]),
    },
    {
      label: "Settings",
      icon: "settings",
      steps: keep([
        { href: "/inventory/warehouses", label: "Warehouses", icon: "warehouses", sees: ["warehouses.view"] },
        { href: "/inventory/catalog/categories", label: "Categories", icon: "categories", sees: ["products.view"] },
        { href: "/inventory/catalog/brands", label: "Brands", icon: "brands", sees: ["products.view"] },
        { href: "/inventory/catalog/units", label: "Units", icon: "units", sees: ["products.view"] },
        { href: "/inventory/admin/audit", label: "Activity log", icon: "auditLog", sees: ["admin.audit"] },
      ]),
    },
  ];
  return { home: may("dashboard.view") ? { href: "/inventory", label: "Home", icon: "home", exact: true } : null, processes, foot };
}

export function Nav({ me, mine = [], waiting = {}, unset = {}, rail = false, actions }: { me: Me; mine?: MyModule[]; waiting?: Waiting; unset?: Unset; rail?: boolean; actions?: ReactNode }) {
  const { home, processes, foot } = menu(me, waiting, unset);
  return (
    <Sidebar
      module="inventory"
      company={me.org?.brandName ?? me.org?.name}
      mine={mine}
      home={home}
      processes={processes}
      foot={foot}
      icon={(name, className) => <Icon name={name as IconName} className={className} />}
      rail={rail}
      actions={actions}
    />
  );
}
