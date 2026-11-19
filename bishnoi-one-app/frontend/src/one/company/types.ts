// The company console (feature plan step 5), as /identity/company gives it.

export type CompanyProfile = {
  id: string;
  no: number | null;
  name: string;
  slug: string;
  status: string;
  currency: string;
  timezone: string;
  /** How numbers and dates are written ("en-PH"), for every app (2026-10-31). */
  locale: string;
  contactEmail: string | null;
  createdAt: string;
  /** The letterhead every printed document carries (step 10). */
  legalName: string | null;
  address: string | null;
  tin: string | null;
  phone: string | null;
  documentFooter: string | null;
  logo: string | null;
};

export type CompanyApp = { key: string; name: string; description: string | null; appUrl: string | null; people: number; administrators: number };

export type SecurityPerson = {
  id: string;
  fullName: string;
  email: string;
  status: "active" | "suspended";
  isCompanyAdmin: boolean;
  hasPassword: boolean;
  passwordChangedAt: string | null;
  lastActiveAt: string | null;
  openSignIns: number;
};

export type SecurityData = { people: SecurityPerson[]; withoutPassword: number; administrators: number; openSignIns: number };

export type ActivityEntry = {
  id: string;
  at: string;
  actor: string;
  action: string;
  category: string;
  target: string;
  fields: string[];
};

/** A person at the company, as the Administrators card lists them (2026-10-30). */
export type AdminPerson = { id: string; fullName: string; email: string; title: string | null; isMe: boolean };
export type Administrators = { administrators: AdminPerson[]; others: AdminPerson[] };
