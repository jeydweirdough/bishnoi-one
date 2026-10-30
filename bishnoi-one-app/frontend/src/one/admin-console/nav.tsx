"use client";

import type { ReactNode } from "react";
import { Sidebar, type Process } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/platform/ui/icons";

/** A group of the console's pages: one sidebar row that opens to them. `operators`: Bishnoi One's own work, at the foot. */
export type ConsoleGroup = { label: string; icon?: IconName; flow?: boolean; operators?: boolean; pages: { href: string; label: string; icon: IconName }[] };

/**
 * The Admin Console's sidebar: the same one every module wears (src/platform/shell/sidebar.tsx). Grouped as the
 * modules are (2026-10-29, the flat list of every page was too long): Home, then one row per area of the company's
 * administration (Company, People, Reports), each opening in place to its pages. Operations (2026-10-30) wears the
 * same sidebar with its own areas; operators' pages are no longer at the Admin Console's foot.
 */
export function ConsoleNav({ module = "platform", groups, mine, company, rail = false, actions }: { module?: "platform" | "operations"; groups: ConsoleGroup[]; mine: MyModule[]; company?: string | null; rail?: boolean; actions?: ReactNode }) {
  const area = (g: ConsoleGroup): Process => ({
    label: g.label, icon: g.icon ?? g.pages[0]?.icon,
    steps: g.pages.map((p) => ({ href: p.href, label: p.label, icon: p.icon, exact: p.href === "/platform/roles" })),
  });
  const homeGroup = groups.find((g) => g.label === "Home" && g.pages.length === 1);
  const home = homeGroup ? { href: homeGroup.pages[0].href, label: homeGroup.pages[0].label, icon: homeGroup.pages[0].icon, exact: true } : null;
  const processes = groups.filter((g) => g !== homeGroup && !g.operators).map(area);
  const foot = groups.filter((g) => g.operators).map(area);
  return (
    <Sidebar
      module={module}
      company={company}
      mine={mine}
      home={home}
      processes={processes}
      foot={foot}
      footLabel={foot.length > 0 ? "Bishnoi One" : undefined}
      icon={(name, className) => <Icon name={name as IconName} className={className} />}
      rail={rail}
      actions={actions}
    />
  );
}
