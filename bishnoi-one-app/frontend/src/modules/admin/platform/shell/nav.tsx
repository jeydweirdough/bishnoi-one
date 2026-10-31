"use client";

import type { ReactNode } from "react";
import { Sidebar, type Missing, type Process, type Step } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/modules/admin/platform/ui/icons";
import type { Me } from "@/src/modules/admin/platform/lib/types";

// Executive Admin's menu, by the work it holds, in standard terms (decided 2026-10-24,
// benchmarks/surpass.md §1): Compliance, Fleet and travel, Service requests, Marketing;
// administration at the foot. The sidebar itself is src/platform/shell/sidebar.tsx.

/** How many things aren't set up yet, by kind (the API's /admin/unset). */
export type Unset = Record<string, number>;

const UNSET_SAYS: Record<string, (n: number) => string> = {
  propertyRent: (n) => `${n} ${n === 1 ? "property has" : "properties have"} no monthly rent`,
  documentExpiry: (n) => `${n} ${n === 1 ? "document has" : "documents have"} no expiry date, so no renewal alert can be sent`,
};

function missingOf(unset: Unset, keys: string[]): Missing {
  const found = keys.filter((key) => unset[key]);
  return { count: found.reduce((n, key) => n + unset[key], 0), says: found.map((key) => UNSET_SAYS[key](unset[key])).join(". ") };
}

type Item = Step & { sees: string };

function menu(me: Me, unset: Unset): { home: Step | null; processes: Process[]; foot: Process[] } {
  // A role that holds the permission reaches the page (the API checks the same).
  const may = (p: string) => me.permissions?.includes(p) ?? me.canManageSettings;
  const keep = (items: Item[]): Step[] => items.filter((i) => may(i.sees)).map(({ sees: _s, ...step }) => step);
  const processes: Process[] = [
    {
      label: "Compliance", icon: "permits",
      steps: keep([
        { href: "/admin/notifications", label: "Renewal alerts", icon: "notifications", sees: "notifications.view" },
        { href: "/admin/permits", label: "Permits", icon: "permits", sees: "permits.view" },
        { href: "/admin/documents", label: "Documents", icon: "documents", sees: "documents.view", missing: missingOf(unset, ["documentExpiry"]) },
        { href: "/admin/immigration", label: "Expatriates", icon: "immigration", sees: "immigration.view" },
        { href: "/admin/properties", label: "Properties", icon: "properties", sees: "properties.view", missing: missingOf(unset, ["propertyRent"]) },
      ]),
    },
    {
      label: "Fleet and travel", icon: "vehicles",
      steps: keep([
        { href: "/admin/vehicles", label: "Vehicles", icon: "vehicles", sees: "vehicles.view" },
        { href: "/admin/fuel-cards", label: "Fuel cards", icon: "fuelCards", sees: "vehicles.view" },
        { href: "/admin/travel", label: "Hotel and flights", icon: "travel", sees: "travel.view" },
        { href: "/admin/devices", label: "Devices issued", icon: "devices", sees: "devices.view" },
      ]),
    },
    { label: "Service requests", icon: "tickets", steps: keep([{ href: "/admin/tickets", label: "Office requests", icon: "tickets", sees: "tickets.view" }]) },
    // Marketing's designs, through review and production to giving them out.
    { label: "Marketing", icon: "approvals", steps: keep([{ href: "/admin/materials", label: "Promotional materials", icon: "approvals", sees: "materials.view" }]) },
    // Reports: one row (decided 2026-10-26); the Reports Center lists its own categories.
    {
      label: "Reports", icon: "reports",
      // One row: the Reports Center lists the categories itself (decided 2026-10-26).
      steps: ["permits.view", "immigration.view", "documents.view", "properties.view", "vehicles.view", "travel.view", "devices.view", "tickets.view", "materials.view"].some(may)
        ? [{ href: "/admin/reports", label: "Reports", icon: "reports" }]
        : [],
    },
  ];
  const foot: Process[] = [
    {
      label: "Settings", icon: "settings",
      steps: [
      ],
    },
  ];
  return { home: may("dashboard.view") ? { href: "/admin", label: "Home", icon: "home", exact: true } : null, processes, foot };
}


export function Nav({ me, mine = [], unset = {}, rail = false, actions }: { me: Me; mine?: MyModule[]; unset?: Unset; rail?: boolean; actions?: ReactNode }) {
  const { home, processes, foot } = menu(me, unset);
  return (
    <Sidebar
      module="admin"
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
