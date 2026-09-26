import type { Me } from "./types";

/** Whether the person's role gives them this permission ("customers.edit", "admin.users"). */
export const can = (me: Me, permission: string): boolean => me.permissions?.includes(permission) ?? false;

/** Who's who: users, their roles, their teams. One place in the sidebar, a sub-page each. */
export const PEOPLE_PAGES = [
  { href: "/admin/users", label: "Users", permission: "admin.users" },
  { href: "/admin/roles", label: "Roles and permissions", permission: "admin.roles" },
  { href: "/admin/teams", label: "Teams", permission: "admin.teams" },
] as const;

export const peoplePagesFor = (me: Me) => PEOPLE_PAGES.filter((t) => can(me, t.permission));

/** Everything an admin sets up for everyone, a sub-page each. The pricing two
 *  are gated on the catalogue, as their pages and the API are. */
export const SETTINGS_PAGES = [
  { href: "/admin/settings", label: "Forms", permission: "admin.settings" },
  { href: "/admin/settings/company", label: "Company and quotes", permission: "admin.settings" },
  { href: "/admin/settings/quote-templates", label: "Quotation templates", permission: "admin.settings" },
  { href: "/admin/settings/customer-types", label: "Customer types", permission: "admin.types" },
  { href: "/admin/settings/pricing", label: "Pricing and retention", permission: "products.view" },
  { href: "/admin/settings/price-rules", label: "Price rules", permission: "products.view" },
  { href: "/admin/settings/funds", label: "Fund purposes", permission: "admin.settings" },
] as const;

export const settingsPagesFor = (me: Me) => SETTINGS_PAGES.filter((t) => can(me, t.permission));

type SubPage = { href: string; label: string };
type AdminPage = { href: string; label: string; icon: "people" | "settings" | "auditLog"; also: string[]; subpages?: SubPage[] };

const sub = (t: { href: string; label: string }): SubPage => ({ href: t.href, label: t.label });

/** The CRM's Administration in the sidebar: three links, each only for a role
 *  that may open it, the first two opening to their own pages while you're in them. */
export function adminPagesFor(me: Me): AdminPage[] {
  const pages: AdminPage[] = [];
  const people = peoplePagesFor(me);
  // It opens on the first sub-page this person may see.
  if (people.length) pages.push({ href: people[0].href, label: "People and access", icon: "people", also: PEOPLE_PAGES.map((t) => t.href), subpages: people.map(sub) });
  if (can(me, "admin.settings") || can(me, "admin.types")) {
    const settings = settingsPagesFor(me);
    pages.push({ href: settings[0].href, label: "Settings", icon: "settings", also: ["/admin/settings"], subpages: settings.map(sub) });
  }
  if (can(me, "admin.audit")) pages.push({ href: "/admin/audit", label: "Audit log", icon: "auditLog", also: [] });
  return pages;
}
