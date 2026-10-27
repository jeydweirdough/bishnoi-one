import type { Supplier, VatKind } from "./types";

export function billTaxDefaults(supplier?: Pick<Supplier, "taxDefaultsConfirmed" | "vatRegistered" | "withholding">): { vat: VatKind | ""; withholding: string } {
  return supplier?.taxDefaultsConfirmed
    ? { vat: supplier.vatRegistered ? "vat" : "none", withholding: supplier.withholding?.code ?? "" }
    : { vat: "", withholding: "unconfirmed" };
}
