import test from "node:test";
import assert from "node:assert/strict";
import * as legacy from "../bir/sales-dat/engine.ts";
import { parseOojeema, parseSRGrid, buildAsIsDAT, addressBook, checkDAT, datToSalesReliefCSV, comparisonCentavos, companySettingsValid } from "../bir/sales-dat/source-safety.ts";

const seller = { tin: "12345678900000", name: "TEST ONLY COMPANY", tradeName: "TEST ONLY COMPANY", address: "FICTIONAL ADDRESS" };
const row = { year: 2026, month: 1, day: 5, tin: "00122233300000", name: "TEST ONLY CUSTOMER", address: "FICTIONAL ADDRESS", gross: 100, exempt: 0, zero: 0, taxable: 100, vat: 12 };
const header = { tin: seller.tin, name: seller.name, trade: seller.tradeName, a1: seller.address, a2: "", rdo: "53A", fy: "12", rate: "12", period: "01/31/2026" };
const source = rows => ({ taxpayer: seller, rows, total: null });
const csv = (amount = "100", total = false) => [
  ["TAXPAYER NAME", seller.name], ["TIN", seller.tin], ["TAXPAYER ADDRESS", seller.address],
  ["JAN 05, 2026", row.tin, row.name, "", row.address, amount, 0, 0, amount, 12],
  ...(total ? [["TOTAL", "", "", "", "", amount, 0, 0, amount, 12]] : []),
].map(r => r.map(v => '"' + String(v).replaceAll('"', '""') + '"').join(",")).join("\r\n");

test("as-is rejects mixed months before repeated-buyer grouping can hide them", () => {
  assert.throws(() => buildAsIsDAT(source([row, { ...row, month: 2 }]), header, null, true), /more than one month/);
  assert.throws(() => buildAsIsDAT(source([row, { ...row, year: 2027 }]), header, null, false), /more than one month/);
});

test("source amounts reject malformed text, infinity and malformed TOTAL cells", () => {
  for (const value of ["not-a-number", "100oops", "Infinity", "1,23.00", "NaN"]) assert.throws(() => parseOojeema(csv(value)), /not a valid amount/);
  const grid = legacy.parseCSV(csv()); grid.push(["TOTAL", "", "", "", "", "broken", 0, 0, 100, 12]);
  assert.throws(() => parseSRGrid(grid, "TEST ONLY.csv"), /row 5.*not a valid amount/);
});

test("valid comma, parentheses, blank and dash money cells keep legacy amounts", () => {
  for (const value of ["1,234.50", "(1,234.50)", "-1234.50", "", "-", ".50"]) {
    const grid = legacy.parseCSV(csv()); grid[3][5] = value; grid[3][8] = value;
    assert.deepEqual(parseSRGrid(grid, "TEST ONLY.csv"), legacy.parseSRGrid(grid, "TEST ONLY.csv"));
  }
});

test("invalid calendar dates, mismatched period and invalid year end are rejected", () => {
  assert.throws(() => buildAsIsDAT(source([{ ...row, month: 2, day: 30 }]), header, null, true), /valid calendar date/);
  assert.throws(() => buildAsIsDAT(source([row]), { ...header, period: "02/28/2026" }, null, true), /same month and year/);
  assert.throws(() => buildAsIsDAT(source([row]), { ...header, period: "01/03/2026" }, null, true), /cover the source/);
  for (const fy of ["", "0", "13", "1.5"]) assert.throws(() => buildAsIsDAT(source([row]), { ...header, fy }, null, true), /year-end month/);
  assert.throws(() => buildAsIsDAT(source([row]), { ...header, tin: "ABC123456789" }, null, true), /seller TIN/);
});

test("valid nine monthly DATs remain byte-identical to legacy output, including RDO53A", () => {
  for (let month = 1; month <= 9; month++) {
    const parsed = source([{ ...row, month }]);
    const h = { ...header, period: String(month).padStart(2, "0") + "/" + new Date(2026, month, 0).getDate() + "/2026" };
    const safe = buildAsIsDAT(parsed, h, null, true).out;
    const old = legacy.buildDAT(parsed, { rdo: "53A", fyMonth: 12 });
    assert.equal(safe.text, old.text); assert.equal(safe.filename, old.filename);
    assert(safe.checks.every(c => c.ok));
    assert.equal(legacy.parseCSV(safe.text)[1][2], "001222333");
  }
});

test("malformed supplied buyer TIN is held; blank customer TIN remains a warning", () => {
  for (const tin of ["123", "ABC123456789", "123456789012345"]) assert.throws(() => buildAsIsDAT(source([{ ...row, tin }]), header, null, true), /supplied customer TIN/);
  const result = buildAsIsDAT(source([{ ...row, tin: "" }]), header, null, true);
  assert(result.issues.some(i => i.sev === "warn" && i.msg.includes("No TIN")));
  assert.equal(legacy.parseCSV(result.out.text)[1][2], "");
});

test("malformed DAT monetary text fails checks and cannot become a zero-valued CSV", () => {
  const valid = legacy.buildDAT(source([row]), { rdo: "53A", fyMonth: 12 });
  const bad = valid.text.replaceAll("100.00", "not-a-number");
  assert(checkDAT(bad, valid.filename, 1).some(c => !c.ok));
  assert.throws(() => datToSalesReliefCSV(bad, {}), /Supporting DAT/);
  assert.equal(datToSalesReliefCSV(valid.text, {}).text, legacy.datToSalesReliefCSV(valid.text, {}).text);
});

test("supporting DAT must belong to the selected seller", () => {
  const other = legacy.buildDAT(source([row]), { rdo: "53A", fyMonth: 12 });
  const book = addressBook(other.text);
  assert.throws(() => buildAsIsDAT(source([row]), { ...header, tin: "98765432100000" }, book, true), /different seller TIN/);
});

test("manual comparison money and supporting year-end settings cannot silently default", () => {
  assert.throws(() => comparisonCentavos("not-a-number"), /not been treated as zero/);
  assert.equal(comparisonCentavos("(1,234.50)"), -123450);
  assert(companySettingsValid("53A", "12"));
  assert(!companySettingsValid("53A", "13"));
  assert(!companySettingsValid("53A", "1e1"));
  const valid = legacy.buildDAT(source([row]), { rdo: "53A", fyMonth: 12 });
  assert.throws(() => addressBook(valid.text.replace(/,12\r\n/, ",13\r\n")), /year-end month/);
});
