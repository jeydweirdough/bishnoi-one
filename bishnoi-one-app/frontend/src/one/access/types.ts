import type { PermissionArea } from "@/src/platform/ui/permission-grid";

// Access in one place (decided 2026-10-23): what Bishnoi One Platform's
// /identity/access answers a company's administrator.

export type AccessModule = {
  /** Its key on the Platform ("crm", "exec"). */
  key: string;
  name: string;
  /** Whether its API answered: its permissions can't be changed while it's out of reach. */
  reachable: boolean;
  areas: PermissionArea[];
  /** Whose records a role may reach there; empty where every role reaches every record. */
  scopes: { key: string; label: string }[];
};

export type AccessRole = {
  id: string;
  name: string;
  description: string | null;
  /** Everything in every module: each one's Administrator. */
  isAdmin: boolean;
  /** By module key. */
  permissions: Record<string, string[]>;
  scopes: Record<string, string>;
  people: number;
};

export type AccessPerson = {
  id: string;
  fullName: string;
  email: string;
  title: string | null;
  status: string;
  isCompanyAdmin: boolean;
  roleId: string | null;
  /** The modules they may open, and the role each gives them today. */
  apps: { key: string; role: string | null }[];
};

export type AccessData = {
  company: { id: string; name: string };
  modules: AccessModule[];
  roles: AccessRole[];
  people: AccessPerson[];
  /** People still to be given a role here (each module goes by its own until then). */
  toChoose: string[];
};

export type RoleInput = {
  name: string;
  description: string | null;
  isAdmin: boolean;
  permissions: Record<string, string[]>;
  scopes: Record<string, string>;
};

export type ImportReport = { rolesMade: number; peopleGiven: number; toChoose: number; unreachable: string[] };
