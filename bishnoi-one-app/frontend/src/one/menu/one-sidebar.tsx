"use client";

import type { ReactNode } from "react";
import { Sidebar } from "@/src/platform/shell/sidebar";
import { Icon, type IconName } from "@/src/platform/ui/icons";

/** The shared sidebar on the one app's own pages (Home, Reports): no module, only the one menu. */
export function OneSidebar({ company, rail, actions }: { company?: string | null; rail: boolean; actions: ReactNode }) {
  return (
    <Sidebar company={company} mine={[]} processes={[]} rail={rail} actions={actions} icon={(name, className) => <Icon name={name as IconName} className={className} />} />
  );
}
