// The CRM's people, settings and audit pages, as the CRM's sidebar and settings tabs list them,
// at /crm/admin/... in the one app (decided 2026-10-23). The other modules keep the kit's lib/access.ts.
import type { Me } from "@/src/platform/lib/types";

/** Whether the person's role gives them this permission ("customers.edit", "admin.users"). */
export const can = (me: Me, permission: string): boolean => me.permissions?.includes(permission) ?? false;

/** Who's who: users, their roles, their teams. One place in the sidebar, a sub-page each. */
/** The Users pages: an administrator for everyone, a manager for the people in the teams they manage. */
export const USERS = ["admin.users", "department.manage"] as const;

export const PEOPLE_PAGES = [
  { href: "/crm/admin/users", label: "Users", permission: USERS },
  { href: "/platform/access/roles", label: "Roles and permissions", permission: "admin.roles" },
  { href: "/crm/admin/teams", label: "Teams", permission: "admin.teams" },
] as const;


/** A manager's own department's settings (its templates, attention rules and
 *  retention windows), beside an administrator's for every department. */
const DEPARTMENT = ["admin.settings", "department.manage"];

/** Everything an admin sets up for everyone, a sub-page each. The pricing two
 *  are gated on the catalogue, as their pages and the API are; the department
 *  ones also open to a manager, for their own departments. */
export const SETTINGS_PAGES = [
  { href: "/crm/admin/settings", label: "Forms", permission: "admin.settings" },
  { href: "/crm/admin/settings/company", label: "Company and quotes", permission: "admin.settings" },
  { href: "/crm/admin/settings/quote-templates", label: "Quotation templates", permission: DEPARTMENT },
  { href: "/crm/admin/settings/customer-types", label: "Customer types", permission: "admin.types" },
  { href: "/crm/admin/settings/terms", label: "Terms", permission: "admin.settings" },
  { href: "/crm/admin/settings/deal-stages", label: "Deal stages", permission: "admin.settings" },
  { href: "/crm/admin/settings/performance", label: "Performance", permission: "admin.settings" },
  { href: "/crm/admin/settings/pricing", label: "Pricing and retention", permission: "products.view" },
  { href: "/crm/admin/settings/retention-windows", label: "Retention windows", permission: DEPARTMENT },
  { href: "/crm/admin/settings/price-rules", label: "Price rules", permission: "products.view" },
  { href: "/crm/admin/settings/associations", label: "Associations", permission: "admin.settings" },
  { href: "/crm/admin/settings/emails", label: "Email templates", permission: "admin.settings" },
  { href: "/crm/admin/settings/attention", label: "Attention", permission: DEPARTMENT },
  { href: "/crm/admin/settings/connections", label: "Connections", permission: "admin.settings" },
] as const satisfies readonly { href: string; label: string; permission: string | readonly string[] }[];

/** Any one of these permissions. */
export const canAny = (me: Me, permission: string | readonly string[]): boolean =>
  typeof permission === "string" ? can(me, permission) : permission.some((p) => can(me, p));

export const peoplePagesFor = (me: Me) => PEOPLE_PAGES.filter((t) => canAny(me, t.permission));

/** A manager without the company's settings sees only their department's. */
export const settingsPagesFor = (me: Me) =>
  SETTINGS_PAGES.filter((t) => canAny(me, t.permission) && (can(me, "admin.settings") || can(me, "admin.types") || t.permission === DEPARTMENT));

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
    pages.push({ href: settings[0].href, label: "Settings", icon: "settings", also: ["/crm/admin/settings"], subpages: settings.map(sub) });
  } else if (can(me, "department.manage")) {
    // A manager: their department's settings only.
    const settings = settingsPagesFor(me);
    pages.push({ href: settings[0].href, label: "Department settings", icon: "settings", also: settings.map((t) => t.href), subpages: settings.map(sub) });
  }
  if (can(me, "admin.audit")) pages.push({ href: "/crm/admin/audit", label: "Audit log", icon: "auditLog", also: [] });
  return pages;
}
