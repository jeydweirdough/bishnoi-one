// Reading suppliers from Zoho's vendor export in the browser (src/modules/finance/payables/csv.ts; 2026-10-23):
// headings as Zoho writes them, the billing address put together, other columns ignored.

import assert from "node:assert/strict";
import test from "node:test";
import { supplierRows } from "../payables/csv.ts";

test("Zoho's vendor columns are read by their headings", () => {
  const csv = [
    "Contact ID,Display Name,Company Name,Salutation,First Name,Last Name,EmailID,Phone,MobilePhone,Payment Terms Label,Billing Address,Billing City,Billing Country,Status,Currency Code,Company ID,Website",
    "460000000012345,SAMPLE PRINTING SERVICES,Sample Printing Services Inc.,Ms.,Ana,Cruz,printing@example.com,02 8000 0000,0917 000 0000,Net 15,1 Test St,Makati,Philippines,Active,PHP,123456789000,printing.example.com",
  ].join("\n");
  assert.deepEqual(supplierRows(csv), [
    {
      name: "SAMPLE PRINTING SERVICES", companyName: "Sample Printing Services Inc.", salutation: "Ms.", firstName: "Ana", lastName: "Cruz",
      email: "printing@example.com", phone: "02 8000 0000", mobile: "0917 000 0000", tin: null, companyId: "123456789000",
      address: "1 Test St, Makati, Philippines", terms: "Net 15", notes: null, status: "Active", currency: "PHP",
    },
  ]);
});

test("a file with only a company name column still reads", () => {
  const [row] = supplierRows("Company Name;Email\nSample Kitchen Corporation;kitchen@example.com\n");
  assert.equal(row.companyName, "Sample Kitchen Corporation");
  assert.equal(row.name, null);
  assert.equal(row.email, "kitchen@example.com");
});

test("a file with no name column isn't a vendor list", () => {
  assert.equal(supplierRows("Date,Amount\n2026-10-01,100\n"), null);
});
