import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { getAccount, type Account } from "@/src/platform/lib/account";
import { OneActions } from "@/src/one/one-actions";
import { myModules } from "@/src/one/mine";
import { ConsoleNav, type ConsoleGroup } from "./nav";

/** What this person may open here: the Platform's own pages for its staff, roles for a company's administrators. */
export function consoleGroups(me: Account): ConsoleGroup[] {
  const groups: ConsoleGroup[] = [];
  if (me.staff)
    groups.push({
      label: "Platform",
      pages: [
        { href: "/platform/apis", label: "APIs", icon: "apps" },
        { href: "/platform/companies", label: "Companies", icon: "companies" },
        { href: "/platform/accounts", label: "Accounts", icon: "people" },
      ],
    });
  if (me.isCompanyAdmin)
    groups.push({
      label: "Users and roles",
      // A role is made, then given to people.
      flow: true,
      pages: [
        { href: "/platform/roles", label: "Roles", icon: "roles" },
        { href: "/platform/roles/people", label: "People", icon: "teams" },
      ],
    });
  if (me.isCompanyAdmin)
    groups.push({
      label: "Reports",
      pages: [
        { href: "/platform/reports", label: "Reports Center", icon: "reports" },
        { href: "/platform/reports/kpis", label: "Company KPIs", icon: "goals" },
      ],
    });
  return groups;
}

/**
 * The Admin Console (decided 2026-10-24): the Platform's screens, in its look,
 * for one Bishnoi One sign-in. Bishnoi One's staff (same email as their staff
 * account) see the APIs, companies and accounts; a company's administrators its
 * roles and who holds them. Framed like every module: sidebar, then your
 * modules and account at the top right.
 */
export async function AdminConsoleFrame({ children }: { children: ReactNode }) {
  const me = await getAccount();
  const rail = (await cookies()).get("bishnoi_nav")?.value === "rail";
  const actions = (
    <div className="flex items-center gap-1">
      <OneActions />
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
