import type { Me } from "@/src/platform/lib/types";
import { can } from "../lib/labels";
import { Tabs } from "./ui";

// Each place's tabs: what belongs to it, one tab each, only the ones this role opens.

export function CatalogTabs({ me, current }: { me: Me; current: string }) {
  return (
    <Tabs
      label="Catalog"
      current={current}
      tabs={[
        { href: "/products", label: "Products" },
        { href: "/catalog/categories", label: "Categories" },
        { href: "/catalog/brands", label: "Brands" },
        { href: "/catalog/units", label: "Units of measure" },
      ].map((t) => ({ ...t, show: can(me, "products.view") }))}
    />
  );
}

export function StockTabs({ current }: { current: string }) {
  return (
    <Tabs
      label="Stock"
      current={current}
      tabs={[
        { href: "/stock", label: "Stock overview" },
        { href: "/movements", label: "Movements" },
        { href: "/batches", label: "Batches & expiry" },
        { href: "/serials", label: "Serial numbers" },
      ]}
    />
  );
}

export function AdjustTabs({ me, current }: { me: Me; current: string }) {
  return (
    <Tabs
      label="Adjustments & counts"
      current={current}
      tabs={[
        { href: "/adjustments", label: "Adjustments", show: can(me, "adjustments.view") },
        { href: "/counts", label: "Inventory counts", show: can(me, "counts.view") },
      ]}
    />
  );
}

export function PurchasingTabs({ me, current }: { me: Me; current: string }) {
  return (
    <Tabs
      label="Purchasing"
      current={current}
      tabs={[
        { href: "/purchase-orders", label: "Purchase orders", show: can(me, "purchasing.view") },
        { href: "/receipts", label: "Receiving", show: can(me, "receiving.view") },
        { href: "/backorders", label: "Backorders", show: can(me, "purchasing.view") },
      ]}
    />
  );
}

export function OrderTabs({ current }: { current: string }) {
  return (
    <Tabs
      label="Orders"
      current={current}
      tabs={[
        { href: "/orders", label: "Orders" },
        { href: "/reservations", label: "Reservations" },
        { href: "/orders?status=issued", label: "Issuance history" },
      ]}
    />
  );
}

export function PeopleTabs({ me, current }: { me: Me; current: string }) {
  return (
    <Tabs
      label="Users & roles"
      current={current}
      tabs={[
        { href: "/admin/users", label: "Users", show: can(me, "admin.users") },
        { href: "/admin/roles", label: "Roles & permissions", show: can(me, "admin.roles") },
      ]}
    />
  );
}
