// Reading a chart of accounts from a CSV in the browser (src/ledger/csv.ts; 2026-10-23):
// Oojeema's and Zoho's headings, quotes, semicolons, Windows line ends.

import assert from "node:assert/strict";
import test from "node:test";
import { chartRows, parseCsv } from "../src/ledger/csv.ts";

test("cells in quotes keep their commas, and a doubled quote is one quote", () => {
  assert.deepEqual(parseCsv('a,b\r\n"Advances to/from GPI, Inc.","say ""hi"""\r\n'), [
    ["a", "b"],
    ["Advances to/from GPI, Inc.", 'say "hi"'],
  ]);
});

test("Oojeema's columns are read by their headings", () => {
  const csv = "﻿Code,Name,Class,Nature,Type,Parent,FS Presentation\n6915-001,Provision for Expired Medicines,Other Expenses,Debit,Child,Loss on Expired Medicines,Income Statement\n";
  assert.deepEqual(chartRows(csv), [
    {
      code: "6915-001", name: "Provision for Expired Medicines", kind: "Other Expenses", nature: "Debit",
      statement: "Income Statement", parent: "Loss on Expired Medicines", description: null,
    },
  ]);
});

test("Zoho's export, with semicolons, is read the same way", () => {
  const csv = "Account Name;Account Code;Account Type;Parent Account;Description\nSponsorships;;Expense;Selling and Marketing;Events\n";
  const [row] = chartRows(csv);
  assert.equal(row.name, "Sponsorships");
  assert.equal(row.code, null);
  assert.equal(row.kind, "Expense");
  assert.equal(row.parent, "Selling and Marketing");
});

test("a file without code and name columns isn't a chart", () => {
  assert.equal(chartRows("Date,Amount\n2026-10-01,100\n"), null);
});
