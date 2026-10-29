// The company console (feature plan step 5), as /identity/company gives it.

export type CompanyProfile = {
  id: string;
  no: number | null;
  name: string;
  slug: string;
  status: string;
  currency: string;
  timezone: string;
  contactEmail: string | null;
  /** Its people's email domain (getmeds.ph): they're added, and sign in, only at it (decided 2026-10-29). */
  emailDomain: string | null;
  createdAt: string;
  /** The letterhead every printed document carries (step 10). */
  legalName: string | null;
  address: string | null;
  tin: string | null;
  phone: string | null;
  documentFooter: string | null;
  logo: string | null;
};

/** Someone whose email isn't at the company's domain: they can't sign in until it's changed. */
export type OffDomainPerson = { id: string; fullName: string; email: string };

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

/** One app in the catalogue (step 6), with the feature switches inside it. */
export type CatalogueEntry = {
  key: string;
  name: string;
  job: string;
  service: string;
  /** Not built yet: shown, can't be turned on. */
  later: boolean;
  on: boolean;
  /** The service it runs in is the company's, or can be added. */
  available: boolean;
  switches: { key: string; label: string; hint: string; later: boolean; on: boolean }[];
};
