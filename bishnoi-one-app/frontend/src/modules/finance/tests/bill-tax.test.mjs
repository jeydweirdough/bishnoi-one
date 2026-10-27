import test from "node:test";
import assert from "node:assert/strict";
import { billTaxDefaults } from "../payables/bill-tax.ts";
test("unconfirmed storage values never silently prefill bill tax choices", () => {
  assert.deepEqual(billTaxDefaults(), {vat:"",withholding:"unconfirmed"});
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:false,vatRegistered:true,withholding:null}), {vat:"",withholding:"unconfirmed"});
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:true,vatRegistered:false,withholding:null}), {vat:"none",withholding:""});
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:true,vatRegistered:true,withholding:{code:"WC158"}}), {vat:"vat",withholding:"WC158"});
});
