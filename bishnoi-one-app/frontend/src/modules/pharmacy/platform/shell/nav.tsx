"use client";

import type { ReactNode } from "react";
import { Sidebar, type Process, type Step } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/modules/pharmacy/platform/ui/icons";
import { adminPagesFor } from "@/src/modules/pharmacy/platform/lib/access";
import type { Me } from "@/src/modules/pharmacy/platform/lib/types";

// The Pharmacy's menu, by process, in standard terms (decided 2026-10-24, benchmarks/surpass.md §1):
// Dispensing (a prescription checked, dispensed, then sold), Customers, Inventory, Approvals,
// Reports; administration at the foot. The sidebar itself is src/platform/shell/sidebar.tsx.

/** How many things aren't set up yet, by kind (/pharmacy/unset). */
export type Unset = Record<string, number>;

type Item = Step & { sees: string };

function menu(me: Me, unset: Unset): { home: Step | null; processes: Process[]; foot: Process[] } {
  const may = (p: string) => me.permissions?.includes(p) ?? false;
  const keep = (items: Item[]): Step[] => items.filter((i) => may(i.sees)).map(({ sees: _s, ...step }) => step);
  const prices = unset.medicinePrices ?? 0;
  const processes: Process[] = [
    {
      label: "Dispensing", icon: "prescriptions",
      flow: true,
      steps: keep([
        { href: "/pharmacy/prescriptions", label: "Prescriptions", icon: "prescriptions", sees: "prescriptions.view" },
        { href: "/pharmacy/dispensing", label: "Dispensing", icon: "dispensing", sees: "dispensing.view" },
        { href: "/pharmacy/sales", label: "Sales", icon: "sales", sees: "sales.view" },
      ]),
    },
    { label: "Customers", icon: "patients", steps: keep([{ href: "/pharmacy/patients", label: "Patients and customers", icon: "patients", sees: "patients.view" }]) },
    {
      label: "Inventory", icon: "stock",
      steps: keep([
        { href: "/pharmacy/medicines", label: "Medicines", icon: "medicines", sees: "medicines.view", missing: prices ? { count: prices, says: `${prices} ${prices === 1 ? "medicine has" : "medicines have"} no price` } : undefined },
        { href: "/pharmacy/batches", label: "Batches and expiry", icon: "batches", sees: "batches.view" },
        { href: "/pharmacy/stock", label: "Stock", icon: "stock", sees: "stock.view" },
        { href: "/pharmacy/suppliers", label: "Suppliers", icon: "suppliers", sees: "suppliers.view" },
      ]),
    },
    { label: "Approvals", icon: "approvals", steps: keep([{ href: "/pharmacy/material-reviews", label: "Promotional materials", icon: "approvals", sees: "materials.view" }]) },
    // Reports: one row (decided 2026-10-26); the Reports Center lists its own categories.
    {
      label: "Reports", icon: "reports",
      steps: may("reports.view")
        ? keep([
            { href: "/pharmacy/reports", label: "Reports", icon: "reports", exact: true, also: ["/pharmacy/reports"], sees: "reports.view" },
          ])
        : [],
    },
  ];
  // As every module: Settings with the Activity log at the foot (people and roles are on the Admin Console, 2026-10-28).
  const admin = adminPagesFor(me).map((p) => ({ href: p.href, label: p.label === "Roles and permissions" ? "Roles" : p.label, icon: p.icon, also: p.also }));
  const foot: Process[] = [
    // People and roles are on the Admin Console; the pharmacists' licence numbers stay here (decided 2026-10-28).
    { label: "Settings", icon: "settings", steps: admin.filter((p) => !p.href.startsWith("/platform/")).map((p) => (p.href.endsWith("/users") ? { ...p, label: "Licences" } : p)) },
  ];
  return { home: may("dashboard.view") ? { href: "/pharmacy", label: "Home", icon: "home", exact: true } : null, processes, foot };
}

export function Nav({ me, mine = [], unset = {}, rail = false, actions }: { me: Me; mine?: MyModule[]; unset?: Unset; rail?: boolean; actions?: ReactNode }) {
  const { home, processes, foot } = menu(me, unset);
  return (
    <Sidebar
      module="pharmacy"
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
