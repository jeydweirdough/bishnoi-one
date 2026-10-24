import type { ReactNode } from "react";
import { getAccount, type Account } from "@/src/platform/lib/account";
import { OneActions } from "@/src/one/one-actions";
import { ModuleBrand } from "@/src/platform/shell/module-brand";
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
      label: "Roles and permissions",
      pages: [
        { href: "/platform/roles", label: "Roles", icon: "roles" },
        { href: "/platform/roles/people", label: "Role assignments", icon: "teams" },
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
  return (
    <div className="lg:grid lg:grid-cols-[auto_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh w-[16.5rem] flex-col overflow-y-auto px-4 py-6 lg:flex print:!hidden">
        <div className="mb-6 px-3">
          <ModuleBrand href="/platform" label="Admin Console" company={me.company?.name} />
        </div>
        <ConsoleNav groups={consoleGroups(me)} />
      </aside>
      <main className="min-w-0 px-4 pt-4 pb-12 sm:px-6 lg:px-8 lg:pt-4">
        <header className="mb-4 flex items-center justify-end gap-1">
          <OneActions />
        </header>
        <div className="mx-auto max-w-[80rem]">{children}</div>
      </main>
    </div>
  );
}
