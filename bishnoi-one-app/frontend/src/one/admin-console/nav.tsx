"use client";

import type { ReactNode } from "react";
import { Sidebar, type Process } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/platform/ui/icons";

export type ConsoleGroup = { label: string; flow?: boolean; pages: { href: string; label: string; icon: IconName }[] };

/** The Admin Console's sidebar: the same one every module wears (src/platform/shell/sidebar.tsx). */
export function ConsoleNav({ groups, mine, company, rail = false, actions }: { groups: ConsoleGroup[]; mine: MyModule[]; company?: string | null; rail?: boolean; actions?: ReactNode }) {
  const processes: Process[] = groups.flatMap((g) => g.pages.map((p) => ({ label: p.label, section: g.label, icon: p.icon, steps: [{ href: p.href, label: p.label, icon: p.icon, exact: p.href === "/platform/roles" }] })));
  return (
    <Sidebar
      module="platform"
      company={company}
      mine={mine}
      processes={processes}
      icon={(name, className) => <Icon name={name as IconName} className={className} />}
      rail={rail}
      actions={actions}
    />
  );
}
