import test from "node:test";
import assert from "node:assert/strict";
import { applyImportTax, filterImportRows, selectedImportRows, recheckedSelection } from "../payables/import-review.ts";

const checked = [
  { line: 1, record: 2, status: "new", reviews: [], supplier: { name: "Example one", tin: "123-456-789" } },
  { line: 2, record: 3, status: "review", reviews: ["Confirm VAT registration"], supplier: { name: "Example two", tin: null } },
  { line: 3, record: 4, status: "here", reviews: [], supplier: { name: "Existing", tin: null } },
  { line: 4, record: 5, status: "duplicate", reviews: [], supplier: { name: "Repeated", tin: null } },
];

test("filtering preserves selections outside the filter and never makes a review row importable", () => {
  const selection = new Set([1, 2]);
  assert.deepEqual(filterImportRows(checked, "", "tax").map(r => r.line), [2]);
  assert.deepEqual(filterImportRows(checked, "EXAMPLE", "all").map(r => r.line), [1, 2]);
  assert.deepEqual(filterImportRows(checked, "3", "review").map(r => r.line), [2]);
  assert.deepEqual(selectedImportRows(checked, selection).map(r => r.line), [1]);
  assert.deepEqual([...selection], [1, 2]);
});

test("rechecking retains deliberate exclusions, selects newly ready rows and removes newly blocked rows", () => {
  const next = checked.map(row => row.line === 2 ? { ...row, status: "new" } : row);
  assert.deepEqual([...recheckedSelection(checked, next, new Set())], [2]);
  assert.deepEqual([...recheckedSelection(checked, next, new Set([1]))], [1, 2]);
  assert.deepEqual([...recheckedSelection(next, checked, new Set([1, 2]))], [1]);
});

test("bulk tax confirmation applies only to the stated matching group, excluding existing/duplicate rows", () => {
  const source = [{ name: "One", review: { missingTinAccepted: true } }, { name: "Two" }, { name: "Existing" }, { name: "Duplicate" }];
  const result = applyImportTax(source, checked.slice(1), false, null);
  assert.equal(result[0], source[0]);
  assert.deepEqual(result[1].review, { vatRegistered: false, withholding: null, taxConfirmed: true });
  assert.equal(result[2], source[2]); assert.equal(result[3], source[3]);
  assert.equal(source[1].review, undefined);
});
