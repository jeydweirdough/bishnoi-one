// The Sales DAT, as the rest of Finance uses it. Import from here, not from engine.ts:
// the engine is kept exactly as the original converter (see README.md), and this is
// the one door into it.

export {
  ADJ_CLASS,
  C,
  LISTING_LABEL,
  buildDAT,
  buildXlsx,
  classify,
  clean,
  fmt,
  nameChanges,
  oneRowPerCustomer,
  parseCSV,
  parseSJ,
  readXlsx,
  reconSheets,
  splitAddr,
  tin9,
  tinMap,
  validate,
  zipStore,
} from "@/src/modules/finance/bir/sales-dat/engine";
export * from "@/src/modules/finance/bir/sales-dat/prepare";
export { RULES, CONFIRMED_BY, OTHERWISE, type Rule } from "@/src/modules/finance/bir/sales-dat/rules";

/** A company's details for the file's first line, from GET /finance/bir/sales-dat (backend app/bir.py). */
export type Company = { tin: string; name: string; rdo: string | null; yearEndMonth: number | null; confirmed: boolean; note: string };

export { addressBook, checkDAT, parseOojeema, parseSRGrid, datToSalesReliefCSV } from "./source-safety";
