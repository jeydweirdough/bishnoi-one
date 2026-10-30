import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { getAccount, type Account } from "@/src/platform/lib/account";
import { OneActions } from "@/src/one/one-actions";
import { myModules } from "@/src/one/mine";
import { ConsoleNav, type ConsoleGroup } from "./nav";

/**
 * The Admin Console (feature plan step 5, 2026-10-28, laid out like Odoo's and Zoho's settings): a company's
 * own administration, for its administrators: Home, Company, People, Reports. Nothing of Bishnoi One's own
 * running is here; that is Operations (operationsGroups, /operations), for operators only (2026-10-30).
 */
export function consoleGroups(me: Account): ConsoleGroup[] {
  const groups: ConsoleGroup[] = [];
  if (me.isCompanyAdmin) {
    // The executive Home first: the company in a few figures (decided 2026-10-28).
    groups.push({ label: "Home", pages: [{ href: "/platform/home", label: "Home", icon: "home" }] });
    groups.push({
      label: "Company",
      icon: "company",
      pages: [
        { href: "/platform/company", label: "Company profile", icon: "company" },
        { href: "/platform/company/apps", label: "Apps", icon: "apps" },
        { href: "/platform/company/integrations", label: "Integrations", icon: "settings" },
        { href: "/platform/company/security", label: "Security", icon: "password" },
        { href: "/platform/company/activity", label: "Activity log", icon: "auditLog" },
      ],
    });
    groups.push({
      label: "People",
      icon: "people",
      pages: [
        { href: "/platform/roles/people", label: "People", icon: "people" },
        { href: "/platform/roles", label: "Roles", icon: "roles" },
        { href: "/platform/organisation", label: "Organisation", icon: "teams" },
      ],
    });
    groups.push({
      label: "Reports",
      icon: "reports",
      pages: [
        { href: "/platform/reports", label: "Reports Center", icon: "reports" },
        { href: "/platform/reports/kpis", label: "Company KPIs", icon: "goals" },
      ],
    });
  }
  return groups;
}

/**
 * Bishnoi One Operations (2026-10-30): what Bishnoi One's operators do for every company, kept out of any
 * company's Admin Console: the companies themselves, accounts and operators, the services (addresses,
 * connections, keys) and troubleshooting (business events between the apps, retried or skipped).
 */
export function operationsGroups(me: Account): ConsoleGroup[] {
  if (!me.staff) return [];
  return [
    {
      label: "Companies",
      icon: "companies",
      pages: [
        { href: "/operations/companies", label: "Companies", icon: "companies" },
        { href: "/operations/people", label: "Find a person", icon: "person" },
        { href: "/operations/operators", label: "Operators", icon: "people" },
      ],
    },
    {
      label: "Services",
      icon: "apps",
      pages: [{ href: "/operations/apis", label: "Services and connections", icon: "apps" }],
    },
    {
      label: "Troubleshooting",
      icon: "alerts",
      pages: [{ href: "/operations/events", label: "Events between apps", icon: "activity" }],
    },
  ];
}

/**
 * The Admin Console (decided 2026-10-24) and Operations (2026-10-30): the Platform's screens, in its look,
 * for one Bishnoi One sign-in, framed like every module: sidebar, then your modules and account at the top
 * right. The same frame, two consoles: a company's administrators get their company; operators Bishnoi One's.
 */
export async function AdminConsoleFrame({ children, console: which = "platform" }: { children: ReactNode; console?: "platform" | "operations" }) {
  const me = await getAccount();
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  const actions = (
    <div className="flex items-center gap-1">
      <OneActions links={[{ href: "/platform/account", label: "Your profile" }]} />
    </div>
  );
  const groups = which === "operations" ? operationsGroups(me) : consoleGroups(me);
  return (
    <div className="group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
      <ConsoleNav module={which} groups={groups} mine={myModules(me)} company={which === "operations" ? "Bishnoi One" : me.company?.name} rail={rail} actions={actions} />
      <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
        <header className="mb-4 hidden items-center justify-end gap-1 lg:flex">{actions}</header>
        <div className="mx-auto max-w-[80rem]">{children}</div>
      </main>
    </div>
  );
}
