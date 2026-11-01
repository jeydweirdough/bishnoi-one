import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";
import { NavProgress } from "@/src/platform/shell/nav-progress";
import { getAccount, type Account } from "@/src/platform/lib/account";
import { OneActions } from "@/src/one/one-actions";
import { myModules } from "@/src/one/mine";
import { ConsoleNav, type ConsoleGroup } from "./nav";
import { CrumbsSlot } from "@/src/platform/shell/crumbs";
import { CRM_SETTINGS, FINANCE_SETTINGS, FINANCE_TABS, INVENTORY_SETTINGS, INVENTORY_TABS } from "./app-settings";

/**
 * The Admin Console (feature plan step 5, 2026-10-28, laid out like Odoo's and Zoho's settings): a company's
 * own administration, for its administrators: Home, People, Company, Apps, Reports (regrouped 2026-11-01). Nothing of Bishnoi One's own
 * running is here; that is Operations (operationsGroups, /operations), for operators only (2026-10-30).
 */
export function consoleGroups(me: Account): ConsoleGroup[] {
  const groups: ConsoleGroup[] = [];
  if (me.isCompanyAdmin) {
    // The executive Home first: the company in a few figures (decided 2026-10-28).
    groups.push({ label: "Home", pages: [{ href: "/platform/home", label: "Home", icon: "home" }] });
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
      label: "Company",
      icon: "company",
      pages: [
        { href: "/platform/company", label: "Company profile", icon: "company" },
        { href: "/platform/company/security", label: "Security", icon: "password" },
        { href: "/platform/company/activity", label: "Activity log", icon: "auditLog" },
        // Every app's deleted records and recycle bin, an app at a time (2026-10-31).
        { href: "/platform/company/data-cleanup", label: "Data clean-up", icon: "lists" },
      ],
    });
    // Everything about the apps in one place (2026-11-01): which are on, how each works, what they connect to.
    // One row per app the company has; its parts are tabs on the page (app-settings.ts). The pages are the
    // app's own (they talk to its API).
    const has = (key: string) => me.apps.some((a) => a.key === key);
    groups.push({
      label: "Apps",
      icon: "apps",
      pages: [
        { href: "/platform/company/apps", label: "Apps and features", icon: "apps" },
        ...(has("crm") ? [{ href: `${CRM_SETTINGS}/company`, label: "CRM", icon: "deals" as const, also: [CRM_SETTINGS] }] : []),
        ...(has("inventory") ? [{ href: INVENTORY_TABS[0].href, label: "Inventory", icon: "inventory" as const, also: [INVENTORY_SETTINGS] }] : []),
        ...(has("finance") ? [{ href: FINANCE_TABS[0].href, label: "Finance", icon: "finance" as const, also: [FINANCE_SETTINGS] }] : []),
        { href: "/platform/company/integrations", label: "Integrations", icon: "settings" },
      ],
    });
    // People reports only (2026-10-30): each app's own reports, money ones too, are in that app.
    groups.push({ label: "Reports", pages: [{ href: "/platform/reports", label: "Reports", icon: "reports" }] });
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
      {/* Says at once that a link was clicked: a bar within the console, the 4-dot loader when opening another app. */}
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
      <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
        <header className="mb-4 hidden items-center gap-3 lg:flex"><CrumbsSlot />{actions}</header>
        <div className="mx-auto max-w-[80rem]">{children}</div>
      </main>
    </div>
  );
}
