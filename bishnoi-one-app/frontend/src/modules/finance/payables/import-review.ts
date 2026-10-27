import type { SupplierRow } from "./csv";
import type { SupplierImportRow } from "./types";

export function filterImportRows(checked: SupplierImportRow[], query: string, filter: string) {
  return checked.filter(row => {
    const issue = filter === "all" || filter === row.status
      || (filter === "missingTin" && !row.supplier.tin)
      || (filter === "tax" && row.reviews.some(value => value.includes("VAT")));
    return issue && `${row.supplier.name} ${row.supplier.companyName ?? ""} ${row.supplier.tin ?? ""} ${row.record}`.toLowerCase().includes(query.toLowerCase());
  });
}

export function applyImportTax(rows: SupplierRow[], matching: SupplierImportRow[], vat: boolean, withholding: string | null) {
  const targets = new Set(matching.filter(row => !["here", "duplicate"].includes(row.status)).map(row => row.line - 1));
  return rows.map((row, index) => targets.has(index) ? { ...row, review: { ...row.review, vatRegistered: vat, withholding, taxConfirmed: true } } : row);
}

export function selectedImportRows(checked: SupplierImportRow[], selected: Set<number>) {
  return checked.filter(row => row.status === "new" && selected.has(row.line));
}

export function recheckedSelection(previous: SupplierImportRow[], next: SupplierImportRow[], selected: Set<number>) {
  const previouslyReady = new Set(previous.filter(row => row.status === "new").map(row => row.line));
  return new Set(next.filter(row => row.status === "new" && (selected.has(row.line) || !previouslyReady.has(row.line))).map(row => row.line));
}
