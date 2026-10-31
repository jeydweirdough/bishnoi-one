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
  /** Its abilities in plain words (step 6), each with its limit where it takes one. */
  abilities: { key: string; limit: number | null }[];
  /** The ready-made job role it was copied from. */
  jobRole: string | null;
};

/** Bishnoi One's abilities and ready-made job roles (/identity/access/abilities, step 6). */
export type AbilityCatalogue = {
  groups: { name: string; abilities: { key: string; label: string; limit: string | null; apps: string[] }[] }[];
  jobRoles: { key: string; name: string; sees: string; abilities: string[]; scopes: Record<string, string>; limits: Record<string, number>; admin: boolean }[];
};

export type AccessPerson = {
  id: string;
  fullName: string;
  email: string;
  title: string | null;
  status: string;
  isCompanyAdmin: boolean;
  roleId: string | null;
  /** The modules they may open: the role each gave them before roles were kept here, and their role in it here
   *  (2026-10-31: a role in each app; their own role when the app has none of its own). */
  apps: { key: string; role: string | null; roleId?: string | null }[];
  /** What each app keeps of its own about them, kept here (2026-10-30): CRM employee ID, licence number, Finance calendar. */
  appDetails?: AppDetails;
};

export type AppDetails = { crm?: { employeeId?: string }; pharmacy?: { licenseNo?: string }; finance?: { calendarOn?: boolean } };

export type AccessData = {
  company: { id: string; name: string };
  modules: AccessModule[];
  roles: AccessRole[];
  people: AccessPerson[];
  /** People still to be given a role here (each module goes by its own until then). */
  toChoose: string[];
  /** The administrator looking (their own row has no Switch off or Delete). */
  meId: string;
  /** How many people are in the recycle bin (2026-10-30). */
  inBin: number;
};

/** A person in the recycle bin: deleted, switched off, restorable. */
export type BinPerson = { id: string; fullName: string; email: string; title: string | null; status: string; deletedAt: string; deletedBy: string | null };

export type RoleInput = {
  name: string;
  description: string | null;
  isAdmin: boolean;
  permissions: Record<string, string[]>;
  scopes: Record<string, string>;
};

export type ImportReport = { rolesMade: number; peopleGiven: number; toChoose: number; unreachable: string[] };
