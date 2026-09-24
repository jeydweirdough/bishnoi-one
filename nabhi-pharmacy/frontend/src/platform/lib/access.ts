import { THIS_APP } from "./apps";
import type { Me } from "./types";

/** Whether the person's role gives them this permission ("customers.edit", "admin.users"). */
export const can = (me: Me, permission: string): boolean => me.permissions?.includes(permission) ?? false;

/** Who's who: users, their roles, their teams. One place, three tabs. */
export const PEOPLE_TABS = [
  { href: "/admin/users", label: "Users", permission: "admin.users" },
  { href: "/admin/roles", label: "Roles & permissions", permission: "admin.roles" },
  { href: "/admin/teams", label: "Teams", permission: "admin.teams" },
] as const;

export const peopleTabsFor = (me: Me) => PEOPLE_TABS.filter((t) => can(me, t.permission));

type AdminPage = { href: string; label: string; icon: "people" | "roles" | "settings" | "auditLog"; also: string[] };

/** The Pharmacy's Administration: its users, what each role may do, and the log of who did what. */
const PHARMACY_ADMIN: (AdminPage & { permission: string })[] = [
  { href: "/admin/users", label: "Users", icon: "people", also: [], permission: "admin.users" },
  { href: "/admin/roles", label: "Roles & permissions", icon: "roles", also: [], permission: "admin.roles" },
  { href: "/admin/audit", label: "Activity log", icon: "auditLog", also: [], permission: "admin.audit" },
];

/** An app's Administration in the sidebar: each link only for a role that may open it. */
export function adminPagesFor(me: Me): AdminPage[] {
  if (THIS_APP === "pharmacy") return PHARMACY_ADMIN.filter((p) => can(me, p.permission));
  const pages: AdminPage[] = [];
  const people = peopleTabsFor(me);
  // It opens on the first tab this person may see.
  if (people.length) pages.push({ href: people[0].href, label: "People & access", icon: "people", also: PEOPLE_TABS.map((t) => t.href) });
  if (can(me, "admin.settings") || can(me, "admin.types")) {
    pages.push({ href: can(me, "admin.settings") ? "/admin/settings" : "/admin/settings/customer-types", label: "Settings", icon: "settings", also: ["/admin/settings"] });
  }
  if (can(me, "admin.audit")) pages.push({ href: "/admin/audit", label: "Audit log", icon: "auditLog", also: [] });
  return pages;
}
