"use client";

import type { ReactNode } from "react";
import { Sidebar, type Missing, type Process, type Step } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/modules/finance/platform/ui/icons";
import type { Me } from "@/src/modules/finance/platform/lib/types";

// Finance's menu as Zoho Books lays it out (decided 2026-10-24, benchmarks/surpass.md §1): Sales,
// Expenses, Approvals, Banking, Accountant, Taxes, Reports, in Zoho's names; users and roles and
// settings at the foot. The sidebar itself is
// src/platform/shell/sidebar.tsx, the same for every module.

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

/** What each page needs, so the menu offers only what the role opens (the API checks the same). */
const NEEDS: [string, string][] = [
  ["/finance/funds", "funds.view"],
  ["/finance/invoices", "invoices.view"],
  ["/finance/bills", "bills.view"],
  ["/finance/bank", "bank.view"],
  ["/finance/ledger/accounts", "accounts.view"],
  ["/finance/ledger/posting", "accounts.view"],
  ["/finance/ledger/categories", "categories.view"],
  ["/finance/ledger", "journal.view"],
  ["/finance/tax", "tax.view"],
  ["/finance/prices", "prices.view"],
  // Preparing BIR files is its own tick; the reports and books are bir.view.
  ["/finance/bir/sales-dat", "bir.prepare"],
  ["/finance/bir", "bir.view"],
  ["/finance/calendar", "calendar.use"],
  ["/finance/admin/users", "admin.users"],
  ["/platform/roles", "admin.roles"],
  ["/finance/admin/audit", "admin.audit"],
  ["/finance", "dashboard.view"],
];

function menu(me: Me, waiting: Waiting, unset: Unset): { home: Step | null; processes: Process[]; foot: Process[] } {
  const may = (p: string) => me.permissions?.includes(p) ?? false;
  const opens = (href: string) => {
    const rule = NEEDS.find(([at]) => (at === "/finance" ? href === at : href === at || href.startsWith(`${at}/`)));
    return rule ? may(rule[1]) : true;
  };
  const keep = (steps: Step[]) => steps.filter((s) => opens(s.href.split("?")[0]));
  // As Zoho Books lays it out: Sales, Expenses, Approvals, Banking, Accountant, Taxes, Reports.
  const processes: Process[] = [
    {
      label: "Sales",
      icon: "letters",
      flow: true,
      steps: keep([
        { href: "/finance/invoices", label: "Invoices", icon: "letters", exact: true },
        { href: "/finance/invoices/receivables", label: "Receivables", icon: "money" },
      ]),
    },
    // Marketing requests: a cash advance is released, its liquidation reviewed, then settled.
    {
      label: "Expenses",
      icon: "payments",
      flow: true,
      steps: keep([
        { href: "/finance/funds", label: "Pending release", icon: "payments", count: waiting.to_release, exact: true },
        { href: "/finance/funds/review", label: "Pending liquidation review", icon: "approvals", count: waiting.to_check },
        { href: "/finance/funds/settlement", label: "Pending settlement", icon: "money", count: waiting.to_settle },
        { href: "/finance/funds/outstanding", label: "Outstanding advances", icon: "history", count: waiting.overdue },
        { href: "/finance/funds/history", label: "Expense history", icon: "lists" },
      ]),
    },
    { label: "Approvals", icon: "approvals", steps: keep([{ href: "/finance/prices", label: "Price approvals", icon: "pricing" }]) },
    { label: "Banking", icon: "money", steps: keep([{ href: "/finance/bank", label: "Bank reconciliation", icon: "money" }]) },
    {
      label: "Accountant",
      icon: "lists",
      steps: keep([
        { href: "/finance/ledger", label: "Journal entries", icon: "lists", exact: true },
        { href: "/finance/ledger/accounts", label: "Chart of accounts", icon: "lists" },
        { href: "/finance/ledger/trial-balance", label: "Trial balance", icon: "reports" },
      ]),
    },
    {
      label: "Taxes",
      icon: "money",
      steps: keep([
        { href: "/finance/bir/vat", label: "VAT return", icon: "money" },
        { href: "/finance/bir/withholding", label: "Withholding tax", icon: "letters" },
        { href: "/finance/bir/lists", label: "Summary lists", icon: "lists" },
        { href: "/finance/bir/sales-dat", label: "BIR files (DAT)", icon: "letters" },
      ]),
    },
    { label: "Calendar", icon: "calendar", steps: keep([{ href: "/finance/calendar", label: "Calendar", icon: "calendar" }]) },
    // Reports: one row (decided 2026-10-26); the Reports Center lists its own categories.
    {
      label: "Reports",
      icon: "reports",
      steps: keep([
        { href: "/finance/reports", label: "Reports", icon: "reports", exact: true, also: ["/finance/reports"] },
        { href: "/finance/bir/statements", label: "Financial statements", icon: "reports" },
        { href: "/finance/bir", label: "Books of accounts", icon: "reports", exact: true },
      ]),
    },
  ];
  const foot: Process[] = [
    {
      label: "Users and roles",
      icon: "people",
      steps: keep([
        { href: "/finance/admin/users", label: "Users", icon: "people" },
        { href: "/platform/roles", label: "Roles", icon: "roles" },
      ]),
    },
    {
      label: "Settings",
      icon: "settings",
      steps: keep([
        { href: "/finance/tax", label: "Taxes", icon: "money", missing: missingOf(unset, ["taxProfile"]) },
        { href: "/finance/invoices/series", label: "Transaction number series", icon: "letters", missing: missingOf(unset, ["invoiceSeries"]) },
        { href: "/finance/ledger/posting", label: "Default accounts", icon: "settings", missing: missingOf(unset, ["postingAccounts"]) },
        { href: "/finance/ledger/categories", label: "Expense categories", icon: "lists", missing: missingOf(unset, ["categoryAccounts"]) },
        { href: "/finance/admin/audit", label: "Activity log", icon: "auditLog" },
      ]),
    },
  ];
  return { home: opens("/finance") ? { href: "/finance", label: "Home", icon: "home", exact: true } : null, processes, foot };
}


/** `actions`: the bell, modules and account (top right); on a phone, beside the menu button. */
export function Nav({ me, mine = [], waiting = {}, unset = {}, rail = false, actions, footer }: { me: Me; mine?: MyModule[]; waiting?: Waiting; unset?: Unset; rail?: boolean; actions?: ReactNode; footer?: ReactNode }) {
  const { home, processes, foot } = menu(me, waiting, unset);
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
