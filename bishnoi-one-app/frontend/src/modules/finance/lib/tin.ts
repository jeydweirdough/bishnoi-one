// A TIN as it's typed: only digits are taken, and the dashes are put in for you
// (asked 2026-10-22). 123456789 -> 123-456-789; with a branch code, 12345678900000
// -> 123-456-789-00000. The API reads it with or without dashes (split_tin).

/** `branch`: whether a branch code may follow the 9 digits (a customer's TIN); the
 *  company's own TIN has its branch code in a box of its own. */
export function formatTin(typed: string, branch = true): string {
  const d = typed.replace(/\D/g, "").slice(0, branch ? 14 : 9);
  return [d.slice(0, 3), d.slice(3, 6), d.slice(6, 9), d.slice(9)].filter(Boolean).join("-");
}
