// Reading suppliers from Zoho's vendor export (CSV) in the browser (2026-10-23): nothing of the
// file is uploaded or kept, only its rows go to the API to be checked. Columns are found by
// their headings, written however Zoho writes them ("EmailID", "Mobile Phone", "Billing City"),
// so other exports with the same headings work too. Plain: tests/supplier-csv.test.mjs runs it.

import { parseCsv } from "@/src/modules/finance/ledger/csv"; // the tests' loader adds ".ts" for plain Node

export type SupplierRow = {
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

/** A heading as a key: lower case, letters and digits only ("EmailID" and "Email ID" match). */
const key = (heading: string) => heading.toLowerCase().replace(/[^a-z0-9]/g, "");

// Each field, and the headings that may hold it.
const HEADINGS: Record<Exclude<keyof SupplierRow, "address">, string[]> = {
  name: ["displayname", "contactname", "vendorname", "suppliername", "name"],
  companyName: ["companyname", "company"],
  salutation: ["salutation"],
  firstName: ["firstname"],
  lastName: ["lastname"],
  email: ["emailid", "email", "emailaddress"],
  phone: ["phone", "workphone"],
  mobile: ["mobilephone", "mobile"],
  tin: ["tin", "taxregistrationnumber", "taxid", "vatregistrationnumber", "trn"],
  companyId: ["companyid"],
  terms: ["paymentterms", "paymenttermslabel", "terms"],
  notes: ["notes", "remarks"],
  status: ["status"],
  currency: ["currencycode", "currency"],
};

// The address, from Zoho's billing columns in this order (or one "Address" column).
const ADDRESS = ["billingaddress", "billingstreet2", "billingcity", "billingstate", "billingcountry", "billingcode", "address"];

/** The suppliers by heading; null when the file has no name column at all. */
export function supplierRows(text: string): SupplierRow[] | null {
  const [head, ...rest] = parseCsv(text);
  if (!head) return null;
  const keys = head.map(key);
  const at = Object.fromEntries(Object.entries(HEADINGS).map(([field, options]) => [field, options.map((o) => keys.indexOf(o)).find((i) => i >= 0) ?? -1])) as Record<
    keyof typeof HEADINGS,
    number
  >;
  if (at.name < 0 && at.companyName < 0) return null;
  const addressAt = ADDRESS.map((o) => keys.indexOf(o)).filter((i) => i >= 0);
  const get = (r: string[], i: number) => (i >= 0 ? (r[i] ?? "").trim() || null : null);
  return rest.map((r) => ({
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
}
