// Reading suppliers from Zoho's vendor export in the browser (src/modules/finance/payables/csv.ts; 2026-10-23):
// headings as Zoho writes them, the billing address put together, other columns ignored.

import assert from "node:assert/strict";
import test from "node:test";
import { supplierRows, supplierFile } from "../payables/csv.ts";

test("Zoho's vendor columns are read by their headings", () => {
  const csv = [
    "Contact ID,Display Name,Company Name,Salutation,First Name,Last Name,EmailID,Phone,MobilePhone,Payment Terms Label,Billing Address,Billing City,Billing Country,Status,Currency Code,Company ID,Website",
    "460000000012345,SAMPLE PRINTING SERVICES,Sample Printing Services Inc.,Ms.,Ana,Cruz,printing@example.com,02 8000 0000,0917 000 0000,Net 15,1 Test St,Makati,Philippines,Active,PHP,123456789000,printing.example.com",
  ].join("\n");
  assert.partialDeepStrictEqual(supplierRows(csv), [
    {
      name: "SAMPLE PRINTING SERVICES", companyName: "Sample Printing Services Inc.", salutation: "Ms.", firstName: "Ana", lastName: "Cruz",
      email: "printing@example.com", phone: "02 8000 0000", mobile: "0917 000 0000", tin: null, companyId: "123456789000",
      address: "1 Test St, Makati, Philippines", terms: "Net 15", notes: null, status: "Active", currency: "PHP",
    },
  ]);
});

test("custom TINs, extra phones and tax hints survive with transparent excluded columns", () => {
  const parsed = supplierFile('Display Name,CF.TIN,TIN,CF.Contact Number,Billing Phone,Payment Terms,Payment Terms Label,Tax Name,Tax Percentage,Track TDS,Contact ID,Unused,Empty\nFictional supplier,12345678900000,987654321000,09990000000,0280000000,120,COD,No Tax,0,true,source-123,something,\n');
  const row = parsed.rows[0];
  assert.equal(row.record, 2);
  assert.deepEqual(row.tinSources, [{ heading: 'CF.TIN', value: '12345678900000' }, { heading: 'TIN', value: '987654321000' }]);
  assert.equal(row.contactNumber, '09990000000');
  assert.equal(row.billingPhone, '0280000000');
  assert.equal(row.terms, '120');
  assert.equal(row.termsLabel, 'COD');
  assert.equal(row.taxName, 'No Tax');
  assert.equal(row.trackTds, 'true');
  assert.equal(row.review, undefined); // no tax/identity decision is invented by the parser
  assert.match(parsed.coverage.find(c => c.heading === 'Contact ID').treatment, /Deferred/);
  assert.match(parsed.coverage.find(c => c.heading === 'Unused').treatment, /Not mapped/);
  assert.equal(parsed.coverage.find(c => c.heading === 'Empty').populated, 0);
});

test("shipping-only addresses are kept separate and multiline records retain record numbering", () => {
  const parsed = supplierFile('Display Name,Shipping Address,Notes,CF.TIN\nExample,Test shipping,"first line\nsecond line",123456789\nOther,,,\n');
  assert.equal(parsed.rows[0].address, null);
  assert.equal(parsed.rows[0].shippingAddress, 'Test shipping');
  assert.equal(parsed.rows[0].notes, 'first line\nsecond line');
  assert.equal(parsed.rows[1].record, 3);
  assert.throws(() => supplierFile('Name,TIN,T.I.N\nExample,123,456'), /Repeated column headings/);
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
