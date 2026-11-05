"use client";

import type { ReactNode } from "react";
import { Sidebar, type Missing, type Process, type Step } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/modules/finance/platform/ui/icons";
import type { Me } from "@/src/modules/finance/platform/lib/types";
import { opens, sectionsFor, type Section } from "./sections";

// Finance's menu as Zoho Books lays it out (decided 2026-10-24, benchmarks/surpass.md §1): Sales,
// Expenses, Approvals, Banking, Accountant, Taxes, Reports, in Zoho's names; users and roles and
// settings at the foot. One row per area since 2026-11-04, its pages as tabs at the top (sections.ts).
// The sidebar itself is src/platform/shell/sidebar.tsx, the same for every module.

/** How many things wait on this person, by kind (Finance's /finance/funds/counts). */
export type Waiting = Record<string, number>;

/** How many things aren't set up yet, by kind (Finance's /finance/unset): an admin's only. */
export type Unset = Record<string, number>;

const UNSET_SAYS: Record<string, (n: number) => string> = {
  postingAccounts: (n) => `${n} default ${n === 1 ? "account isn't" : "accounts aren't"} set, so some fund steps can't be posted`,
  categoryAccounts: (n) => `${n} expense ${n === 1 ? "category has" : "categories have"} no account`,
  taxProfile: () => "The company's tax registration isn't complete",
  invoiceSeries: () => "There are no invoice numbers left: add the series from the BIR's Authority to Print",
};

function missingOf(unset: Unset, keys: string[]): Missing {
  const found = keys.filter((key) => unset[key]);
  return { count: found.reduce((n, key) => n + unset[key], 0), says: found.map((key) => UNSET_SAYS[key](unset[key])).join(". ") };
}

/** An area as one sidebar row: it opens the first tab this person may see, and stays lit on all of them. */
function row(section: Section, waiting: Waiting): Process {
  const [first, ...rest] = section.tabs;
  const step: Step = { href: first.href, label: section.label, icon: section.icon, exact: section.exact, also: [...rest.map((t) => t.href), ...(section.also ?? [])] };
  // Marketing requests: what waits at each stage (kept from before the areas were rows).
  if (section.key === "funds") step.count = (["to_release", "to_check", "to_settle", "overdue"] as const).reduce((n, key) => n + (waiting[key] ?? 0), 0);
  return { label: section.label, icon: section.icon, steps: [step] };
}

function menu(me: Me, waiting: Waiting): { home: Step | null; processes: Process[]; foot: Process[] } {
  const sections = sectionsFor(me);
  return {
    home: opens(me, "/finance") ? { href: "/finance", label: "Home", icon: "home", exact: true } : null,
    processes: sections.filter((s) => !s.foot).map((s) => row(s, waiting)),
    foot: sections.filter((s) => s.foot).map((s) => row(s, waiting)),
  };
}


/** `actions`: the bell, modules and account (top right); on a phone, beside the menu button. */
export function Nav({ me, mine = [], waiting = {}, unset = {}, rail = false, actions, footer }: { me: Me; mine?: MyModule[]; waiting?: Waiting; unset?: Unset; rail?: boolean; actions?: ReactNode; footer?: ReactNode }) {
  const { home, processes, foot } = menu(me, waiting);
  return (
    <Sidebar
      module="finance"
      company={me.org?.brandName ?? me.org?.name}
      mine={mine}
      home={home}
      processes={processes}
      foot={foot}
      icon={(name, className) => <Icon name={name as IconName} className={className} />}
      rail={rail}
      actions={actions}
      footer={footer}
    />
  );
}
