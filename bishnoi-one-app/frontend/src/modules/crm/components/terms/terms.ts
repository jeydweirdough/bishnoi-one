// The CRM's words. Standard terms only, as Zoho names things (decided 2026-10-24): a company's
// own words (Settings → Terms, the API's app/terms.py) are no longer shown. What still applies
// from there is which customer type field agents visit (visitedType), which is a setting, not a word.
import type { Me } from "@/src/platform/lib/types";

export type Terms = {
  /** Who field agents visit: "Account(s)", "Doctor(s)" at GetMeds. */
  visited: { one: string; many: string };
  /** The customer type they are (its code), or null for any customer. */
  visitedType: string | null;
  /** Talking through products on a visit: "Product presentation", "Detailing". */
  detailing: string;
  /** Where a visit happens: "Location", "Clinic". */
  site: string;
  /** A product's base name, shared by its brands: "Product family", "Molecule". */
  genericName: string;
};

export const GENERAL_TERMS: Terms = {
  visited: { one: "Account", many: "Accounts" },
  visitedType: null,
  detailing: "Product presentation",
  site: "Location",
  genericName: "Product family",
};

/** The CRM's standard words, with the company's choice of which customers field agents visit. */
export function termsOf(me: Pick<Me, "org"> | null | undefined): Terms {
  return { ...GENERAL_TERMS, visitedType: me?.org?.terms?.visitedType ?? null };
}

/** "Doctor" -> "doctor", for the middle of a sentence. */
export const lower = (word: string) => word.charAt(0).toLowerCase() + word.slice(1);

/** One or many, with its count: "1 doctor", "3 doctors". */
export function counted(n: number, t: Terms): string {
  return `${n} ${lower(n === 1 ? t.visited.one : t.visited.many)}`;
}

/** A general label in the company's words: "Accounts visited" -> "Doctors visited". */
export function worded(text: string, t: Terms): string {
  return text.replace(/Accounts/g, t.visited.many).replace(/accounts/g, lower(t.visited.many)).replace(/Account/g, t.visited.one).replace(/account/g, lower(t.visited.one));
}
