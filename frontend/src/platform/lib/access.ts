import type { Me } from "./types";

/** Whether the person's role gives them this permission ("customers.edit", "admin.users"). */
export const can = (me: Me, permission: string): boolean => me.permissions?.includes(permission) ?? false;

/** Sales' Administration pages, and the permission each one needs. */
export const ADMIN_PAGES = [
  { href: "/admin/users", label: "Users", icon: "people", permission: "admin.users" },
  { href: "/admin/roles", label: "Roles & permissions", icon: "roles", permission: "admin.roles" },
  { href: "/admin/teams", label: "Teams", icon: "teams", permission: "admin.teams" },
  { href: "/admin/audit", label: "Audit log", icon: "auditLog", permission: "admin.audit" },
] as const;

export const adminPagesFor = (me: Me) => ADMIN_PAGES.filter((p) => can(me, p.permission));
