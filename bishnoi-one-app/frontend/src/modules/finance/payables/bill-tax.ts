import type { Supplier, VatKind } from "./types";

// A line's withholding as the bill form holds it: a code, "none:<reason>" (app/payables.py NO_WITHHOLDING), or
// "unconfirmed" until someone chooses (Batch A, 2026-11-05: every local line says what's withheld, or why nothing is).
export const FOREIGN = "none:foreign";

/** Decided by the user 2026-11-05 (app/payables.py origin_by_name): "Ltd" or "Limited" in the name is foreign, every
 *  other name local. It fills the supplier form's choice; a person can change it. */
export function originByName(name: string): "local" | "foreign" {
  return /\b(ltd|limited)\b/i.test(name) ? "foreign" : "local";
}

type TaxedSupplier = Pick<Supplier, "taxDefaultsConfirmed" | "vatRegistered" | "withholding" | "origin" | "vatVariesByItem">;

/** What a new line from this supplier starts with. A foreign supplier is never withheld from; a supplier whose items
 *  differ in VAT (e.g. medicines) leaves VAT to be chosen per line; an unconfirmed one leaves both to be chosen. */
export function billTaxDefaults(supplier?: TaxedSupplier): { vat: VatKind | ""; withholding: string } {
  const vat: VatKind | "" = !supplier?.taxDefaultsConfirmed || supplier.vatVariesByItem ? "" : supplier.vatRegistered ? "vat" : "none";
  if (supplier?.origin === "foreign") return { vat, withholding: FOREIGN };
  return { vat, withholding: supplier?.taxDefaultsConfirmed && supplier.withholding ? supplier.withholding.code : "unconfirmed" };
}

/** A saved line's choice, back in the form: its code, its reason, or still to choose. */
export function withholdingChoice(line: { withholding?: string | null; noWithholding?: string | null }): string {
  return line.withholding || (line.noWithholding ? `none:${line.noWithholding}` : "unconfirmed");
}

/** The choice as the API takes it. A foreign supplier's reason is filled in by the API itself. */
export function withholdingPayload(choice: string, note: string): { withholding: string | null; noWithholdingReason: string | null; noWithholdingNote: string | null } {
  if (choice === "unconfirmed" || choice === FOREIGN) return { withholding: null, noWithholdingReason: null, noWithholdingNote: null };
  if (choice.startsWith("none:")) {
    const reason = choice.slice(5);
    return { withholding: null, noWithholdingReason: reason, noWithholdingNote: reason === "other" ? note.trim() || null : null };
  }
  return { withholding: choice, noWithholdingReason: null, noWithholdingNote: null };
}
