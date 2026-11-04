// Input/output safeguards around the unchanged historical converter engine.
import * as legacy from "./engine";

export type Header = { tin: string; name: string; trade: string; a1: string; a2: string; period: string; rdo: string; fy: string; rate: string };
// The historical engine has an untyped report model; do not change its tax rules here.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Report = any;

function validDay(year: number, month: number, day: number) {
  return year >= 1900 && year <= 9999 && month >= 1 && month <= 12 && day >= 1 && day <= new Date(year, month, 0).getDate();
}

function checkAmount(value: unknown, row: number, label: string) {
  if (typeof value === "number" && Number.isFinite(value)) return;
  const text = String(value ?? "").trim();
  if (text === "" || text === "-") return; // Explicit empty/dash cells in the source represent zero.
  const core = /^\(.*\)$/.test(text) ? text.slice(1, -1) : text;
  if (!/^[+-]?(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?|\.\d+)$/.test(core) || !Number.isFinite(Number(core.replaceAll(",", "")))) {
    throw new Error(`Sales Relief row ${row}: ${label} is not a valid amount. Correct the source value; it has not been replaced with zero.`);
  }
}

export function comparisonCentavos(value: string): number {
  try { checkAmount(value, 0, "Income Statement amount"); }
  catch { throw new Error("Enter a valid Income Statement amount. Invalid text has not been treated as zero."); }
  return legacy.C(value);
}

export function companySettingsValid(rdo: string, fy: string): boolean {
  return /^[A-Za-z0-9]+$/.test(rdo.trim()) && /^\d{1,2}$/.test(fy.trim()) && Number(fy) >= 1 && Number(fy) <= 12;
}

function checkSalesGrid(grid: unknown[][]) {
  const labels = ["Gross sales", "Exempt sales", "Zero-rated sales", "Taxable sales", "Output VAT"];
  grid.forEach((row, i) => {
    const first = String(row[0] ?? "").trim().toUpperCase().replace(/[\s:]+$/, "");
    if (/^(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{1,2},\s*\d{4}$/.test(first) || /^TOTAL/.test(first)) {
      labels.forEach((label, j) => checkAmount(row[j + 5], i + 1, label));
    }
  });
}

function checkDates(parsed: Report) {
  for (const row of parsed.rows) {
    if (!validDay(row.year, row.month, row.day)) throw new Error(`Sales Relief row ${row.row}: the transaction date is not a valid calendar date.`);
  }
}

export function parseOojeema(text: string): Report {
  checkSalesGrid(legacy.parseCSV(text));
  const parsed = legacy.parseOojeema(text);
  checkDates(parsed);
  return parsed;
}

export function parseSRGrid(grid: unknown[][], from: string): Report {
  checkSalesGrid(grid);
  const parsed = legacy.parseSRGrid(grid, from);
  checkDates(parsed);
  return parsed;
}

export function checkDAT(text: string, filename: string, count: number | null): { ok: boolean; label: string }[] {
  const checks = legacy.checkDAT(text, filename, count);
  const records = legacy.parseCSV(text).filter((row: string[]) => row.length > 1);
  const header = records[0] ?? [], details = records.slice(1);
  const numeric = (value: string) => /^-?\d+(?:\.\d{1,2})?$/.test(value ?? "");
  checks.push({ ok: header.slice(10, 14).every(numeric) && details.every((r: string[]) => r.slice(9, 13).every(numeric)), label: "Every monetary field is a valid numeric amount" });
  checks.push({ ok: /^\d{9}$/.test(header[2] ?? "") && details.every((r: string[]) => !r[2] || /^\d{9}$/.test(r[2])), label: "Seller TIN has nine digits; supplied buyer TINs have nine digits" });
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(header[15] ?? "");
  checks.push({ ok: !!m && validDay(Number(m[3]), Number(m[1]), Number(m[2])), label: "Reporting period is a valid calendar date" });
  checks.push({ ok: companySettingsValid(header[14] ?? "", header[16] ?? ""), label: "RDO code is present and year-end month is from 1 to 12" });
  checks.push({ ok: header[1] === "S" && details.every((r: string[]) => r[1] === "S"), label: "Header and details are Sales DAT records" });
  return checks;
}

export function addressBook(text: string): Report {
  const records = legacy.parseCSV(text);
  const header = records.find((r: string[]) => r[0] === "H");
  if (!header) throw new Error("The supporting DAT has no header.");
  const m = /^(\d{2})\/\d{2}\/(\d{4})$/.exec(header[15] ?? "");
  const filename = m ? `${header[2]}S${m[1]}${m[2]}.DAT` : "";
  const failed = checkDAT(text, filename, null).find(c => !c.ok);
  if (failed) throw new Error(`Supporting DAT: ${failed.label}.`);
  const book: Report = legacy.addressBook(text);
  if (book.header) book.header.tin = header[2];
  return book;
}

export function datToSalesReliefCSV(text: string, tins: Record<string, string>): Report {
  // Reuse the same checks before reading money back, so malformed amounts cannot become zero.
  addressBook(text);
  const records = legacy.parseCSV(text);
  if (records.some((r: string[]) => (r[0] === "H" ? [r[3], r[7], r[8], r[9]] : [r[3], r[7], r[8]]).some(v => /^[=+@\t\r]/.test(v ?? "")))) {
    throw new Error("The DAT contains formula-like text. Review the original text before preparing a spreadsheet.");
  }
  return legacy.datToSalesReliefCSV(text, tins);
}

export function buildAsIsDAT(parsed: Report, h: Header, book: Report, perCustomer: boolean): Report {
  if (!parsed.rows.length) throw new Error("No sales rows found.");
  checkDates(parsed);
  const first = parsed.rows[0];
  if (parsed.rows.some((r: Report) => r.year !== first.year || r.month !== first.month)) {
    throw new Error("This file contains more than one month. Use Prepare monthly DAT or choose a Sales Relief file for one month; rows have not been relabelled.");
  }
  const period = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(h.period.trim());
  if (!period || !validDay(Number(period[3]), Number(period[1]), Number(period[2]))) throw new Error("Enter a valid period ending as MM/DD/YYYY.");
  if (Number(period[1]) !== first.month || Number(period[3]) !== first.year || parsed.rows.some((r: Report) => r.day > Number(period[2]))) throw new Error("The period ending must cover the source transactions in the same month and year.");
  const fy = Number(h.fy), rate = Number(h.rate);
  if (!/^\d{1,2}$/.test(h.fy.trim()) || !Number.isInteger(fy) || fy < 1 || fy > 12) throw new Error("Enter the year-end month from 1 to 12.");
  if (!/^[A-Za-z0-9]+$/.test(h.rdo.trim())) throw new Error("Enter the RDO code, including its letter where applicable.");
  if (!/^[\d\s-]+$/.test(h.tin.trim()) || !/^\d{9}(?:\d{3,5})?$/.test(h.tin.replace(/[\s-]/g, "")) || !legacy.clean(h.name, undefined)) throw new Error("Check the seller TIN and registered name in Header details.");
  if (!Number.isFinite(rate) || rate <= 0) throw new Error("Enter a valid VAT rate for the comparison.");
  for (const row of parsed.rows) {
    const tin = String(row.tin ?? "").trim();
    if (tin && (!/^[\d\s-]+$/.test(tin) || !/^\d{9}(?:\d{3,5})?$/.test(tin.replace(/[\s-]/g, "")))) {
      throw new Error("Correct the supplied customer TIN in the source; unknown customer TINs may stay blank, but malformed values are not replaced or shortened.");
    }
  }
  if (book?.header?.tin && book.header.tin !== legacy.tin9(h.tin)) throw new Error("The supporting DAT belongs to a different seller TIN. Choose the correct file.");
  const issues = legacy.validate(parsed, rate);
  const problem = issues.find((i: Report) => i.sev === "error");
  if (problem) throw new Error(`Correct the source before preparing the DAT: ${problem.msg}`);
  const p = JSON.parse(JSON.stringify(parsed));
  const merge = perCustomer ? legacy.oneRowPerCustomer(p.rows) : null;
  if (merge) p.rows = merge.rows;
  Object.assign(p.taxpayer, { tin: h.tin, name: h.name, tradeName: h.trade });
  const out: Report = legacy.buildDAT(p, { book, rdo: h.rdo.trim(), fyMonth: fy, day: Number(period[2]) });
  const lines = out.text.split("\r\n");
  const header = legacy.parseCSV(lines[0] + "\n")[0];
  header[8] = legacy.clean(h.a1, 30); header[9] = legacy.clean(h.a2, 30);
  lines[0] = header.map((v: string, i: number) => [2,3,4,5,6,7,8,9,14].includes(i) ? '"' + v + '"' : v).join(",");
  out.text = lines.join("\r\n");
  out.checks = checkDAT(out.text, out.filename, p.rows.length);
  const failed = out.checks.find((c: { ok: boolean; label: string }) => !c.ok);
  if (failed) throw new Error(`The DAT failed its file check: ${failed.label}.`);
  return { out, merge, rows: p.rows, issues };
}
