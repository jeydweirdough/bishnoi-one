"use client";

import type { ReactNode } from "react";
import { Sidebar, type Process } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/modules/inventory/platform/ui/icons";
import type { Me } from "@/src/modules/inventory/platform/lib/types";

// The Sales app's menu (feature plan step 11): its orders, the ones waiting for approval, and the deliveries they make
// (Inventory's, a click away). The sidebar is the shared one.

export function SalesNav({ me, mine, waiting, rail, actions }: { me: Me; mine: MyModule[]; waiting: number; rail: boolean; actions: ReactNode }) {
  const may = (p: string) => me.permissions?.includes(p) ?? false;
  const processes: Process[] = [
    {
      label: "Sales",
      icon: "issuance",
      steps: [
        { href: "/sales", label: "Sales orders", icon: "issuance", exact: true, also: ["/sales/orders"] },
        ...(may("sales.approve") ? [{ href: "/sales?status=pending", label: "Waiting for approval", icon: "approvals", count: waiting || undefined }] : []),
        ...(may("orders.view") ? [{ href: "/inventory/orders?kind=sale", label: "Deliveries", icon: "issuance" }] : []),
      ],
    },
  ];
  return (
    <Sidebar
      module="sales"
      company={me.org?.brandName ?? me.org?.name}
      mine={mine}
      processes={processes}
      icon={(name, className) => <Icon name={name as IconName} className={className} />}
      rail={rail}
      actions={actions}
    />
  );
}
