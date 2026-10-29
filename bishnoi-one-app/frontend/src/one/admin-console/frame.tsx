import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { getAccount, type Account } from "@/src/platform/lib/account";
import { OneActions } from "@/src/one/one-actions";
import { myModules } from "@/src/one/mine";
import { ConsoleNav, type ConsoleGroup } from "./nav";

/**
 * What this person may open here (feature plan step 5, 2026-10-28, laid out like Odoo's and Zoho's
 * settings): the company console for a company's administrators (Home, Company, People, Reports),
 * and the small Operations area for Bishnoi One's operators.
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
  // Bishnoi One's own work, for operators only: kept apart, under a line at the foot (2026-10-29).
  if (me.staff) {
    groups.push({
      label: "Companies and people",
      icon: "companies",
      operators: true,
      pages: [
        { href: "/platform/companies", label: "Companies", icon: "companies" },
        { href: "/platform/people", label: "Find a person", icon: "person" },
        { href: "/platform/operators", label: "Operators", icon: "people" },
      ],
    });
    groups.push({
      label: "Services",
      icon: "apps",
      operators: true,
      pages: [
        { href: "/platform/apis", label: "Services", icon: "apps" },
        { href: "/platform/events", label: "Events", icon: "activity" },
      ],
    });
  }
  return groups;
}

/**
 * The Admin Console (decided 2026-10-24): the Platform's screens, in its look,
 * for one Bishnoi One sign-in. Operators (a switch on their account) see the Operations area; a
 * company's administrators its company console. Framed like every module: sidebar, then your
 * modules and account at the top right.
 */
export async function AdminConsoleFrame({ children }: { children: ReactNode }) {
  const me = await getAccount();
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  const actions = (
    <div className="flex items-center gap-1">
      <OneActions links={[{ href: "/platform/account", label: "Your profile" }]} />
    </div>
  );
  return (
    <div className="group/shell lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
      <ConsoleNav groups={consoleGroups(me)} mine={myModules(me)} company={me.company?.name} rail={rail} actions={actions} />
      <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
        <header className="mb-4 hidden items-center justify-end gap-1 lg:flex">{actions}</header>
        <div className="mx-auto max-w-[80rem]">{children}</div>
      </main>
    </div>
  );
}
