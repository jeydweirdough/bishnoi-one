// Reading suppliers from Zoho's vendor export (CSV) in the browser (2026-10-23): nothing of the
// file is uploaded or kept, only its rows go to the API to be checked. Columns are found by
// their headings, written however Zoho writes them ("EmailID", "Mobile Phone", "Billing City"),
// so other exports with the same headings work too. Plain: tests/supplier-csv.test.mjs runs it.

import { parseCsv } from "@/src/modules/finance/ledger/csv"; // the tests' loader adds ".ts" for plain Node

export type SupplierRow = {
  record?: number;
  tinSources?: { heading: string; value: string }[];
  contactNumber?: string | null;
  billingPhone?: string | null;
  billingAttention?: string | null;
  designation?: string | null;
  website?: string | null;
  shippingAddress?: string | null;
  termsLabel?: string | null;
  taxName?: string | null;
  taxPercentage?: string | null;
  taxType?: string | null;
  taxable?: string | null;
  trackTds?: string | null;
  accountsPayable?: string | null;
  review?: SupplierReview;
  name: string | null;
  companyName: string | null;
  salutation: string | null;
  firstName: string | null;
  lastName: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  tin: string | null;
  companyId: string | null;
  address: string | null;
  terms: string | null;
  notes: string | null;
  status: string | null;
  currency: string | null;
};

export type SupplierReview = {
  tin?: string | null; tinConfirmed?: boolean; missingTinAccepted?: boolean;
  vatRegistered?: boolean | null; withholding?: string | null; taxConfirmed?: boolean;
  termsDays?: number | null; termsConfirmed?: boolean;
  addressChoice?: "billing" | "shipping" | "missing" | null;
  payablesAccountId?: string | null; accountConfirmed?: boolean; branchConfirmed?: boolean;
  notes?: string | null;
};
export type ColumnCoverage = { heading: string; populated: number; treatment: string };

/** A heading as a key: lower case, letters and digits only ("EmailID" and "Email ID" match). */
const key = (heading: string) => heading.toLowerCase().replace(/[^a-z0-9]/g, "");

// Each field, and the headings that may hold it.
const HEADINGS = {
  name: ["displayname", "contactname", "vendorname", "suppliername", "name"],
  companyName: ["companyname", "company"],
  salutation: ["salutation"],
  firstName: ["firstname"],
  lastName: ["lastname"],
  email: ["emailid", "email", "emailaddress"],
  phone: ["phone", "workphone"],
  mobile: ["mobilephone", "mobile"],
  tin: ["tin", "cftin", "taxregistrationnumber", "taxid", "vatregistrationnumber", "trn"],
  companyId: ["companyid"],
  terms: ["paymentterms", "paymenttermslabel", "terms"],
  notes: ["notes", "remarks"],
  status: ["status"],
  currency: ["currencycode", "currency"],
  contactNumber: ["cfcontactnumber"], billingPhone: ["billingphone"],
  billingAttention: ["billingattention"], designation: ["designation"], website: ["website"],
  termsLabel: ["paymenttermslabel"], taxName: ["taxname"], taxPercentage: ["taxpercentage"],
  taxType: ["taxtype"], taxable: ["taxable"], trackTds: ["tracktds"], accountsPayable: ["accountspayable"],
};

// The address, from Zoho's billing columns in this order (or one "Address" column).
const ADDRESS = ["billingaddress", "billingstreet2", "billingcity", "billingstate", "billingcountry", "billingcode", "address"];

/** The suppliers by heading; null when the file has no name column at all. */
export function supplierFile(text: string): { rows: SupplierRow[]; coverage: ColumnCoverage[] } | null {
  const [head, ...rest] = parseCsv(text);
  if (!head) return null;
  const keys = head.map(key);
  if (new Set(keys).size !== keys.length) throw new Error("Repeated column headings: give each column a unique heading before importing.");
  const at = Object.fromEntries(Object.entries(HEADINGS).map(([field, options]) => [field, options.map((o) => keys.indexOf(o)).find((i) => i >= 0) ?? -1])) as Record<
    keyof typeof HEADINGS,
    number
  >;
  if (at.name < 0 && at.companyName < 0) return null;
  const addressAt = ADDRESS.map((o) => keys.indexOf(o)).filter((i) => i >= 0);
  const get = (r: string[], i: number) => (i >= 0 ? (r[i] ?? "").trim() || null : null);
  const shipping = ["shippingaddress", "shippingstreet2", "shippingcity", "shippingstate", "shippingcountry", "shippingcode"];
  const rows = rest.map((r, index) => ({
    record: index + 2,
    tinSources: keys.flatMap((k, i) => HEADINGS.tin.includes(k) && get(r, i) ? [{ heading: head[i], value: get(r, i)! }] : []),
    ...Object.fromEntries(["contactNumber", "billingPhone", "billingAttention", "designation", "website", "termsLabel", "taxName", "taxPercentage", "taxType", "taxable", "trackTds", "accountsPayable"].map(field => [field, get(r, at[field as keyof typeof HEADINGS])])),
    shippingAddress: shipping.map(k => get(r, keys.indexOf(k))).filter(Boolean).join(", ") || null,
    name: get(r, at.name),
    companyName: get(r, at.companyName),
    salutation: get(r, at.salutation),
    firstName: get(r, at.firstName),
    lastName: get(r, at.lastName),
    email: get(r, at.email),
    phone: get(r, at.phone),
    mobile: get(r, at.mobile),
    tin: get(r, at.tin),
    companyId: get(r, at.companyId),
    address: addressAt.map((i) => get(r, i)).filter(Boolean).join(", ") || null,
    terms: get(r, at.terms),
    notes: get(r, at.notes),
    status: get(r, at.status),
    currency: get(r, at.currency),
  }));
  const deferred = new Set(["contactid", "cfcustomid", "primarycontactid", "cfcreatorid"]);
  const coverage = head.map((heading, i) => {
    const field = Object.entries(HEADINGS).find(([, aliases]) => aliases.includes(keys[i]))?.[0];
    const treatment = field ? ["taxName", "taxPercentage", "taxType", "taxable", "trackTds", "accountsPayable"].includes(field) ? "Retained hint; confirm accounting choices when used" : "Captured; inspect saved-value preview"
      : ADDRESS.includes(keys[i]) ? "Captured billing address"
      : shipping.includes(keys[i]) ? "Retained shipping-address alternative; not substituted for billing"
      : deferred.has(keys[i]) ? "Deferred source identity; not saved in this import"
      : "Not mapped; excluded from saved supplier";
    return { heading, populated: rest.filter(r => get(r, i)).length, treatment };
  });
  return { rows, coverage };
}

export function supplierRows(text: string): SupplierRow[] | null { return supplierFile(text)?.rows ?? null; }
