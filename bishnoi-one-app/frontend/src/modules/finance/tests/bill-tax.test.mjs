import test from "node:test";
import assert from "node:assert/strict";
import { billTaxDefaults, withholdingChoice, withholdingPayload } from "../payables/bill-tax.ts";
test("unconfirmed storage values never silently prefill bill tax choices", () => {
  assert.deepEqual(billTaxDefaults(), {vat:"",withholding:"unconfirmed"});
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:false,vatRegistered:true,withholding:null}), {vat:"",withholding:"unconfirmed"});
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:true,vatRegistered:true,withholding:{code:"WC158"}}), {vat:"vat",withholding:"WC158"});
});
// Batch A (2026-11-05): a local line says why nothing is withheld; a foreign one never is; VAT can be per item.
test("no usual withholding still asks why on each line", () => {
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:true,vatRegistered:false,withholding:null,origin:"local"}), {vat:"none",withholding:"unconfirmed"});
});
test("a foreign supplier is never withheld from, even with an old usual code", () => {
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:true,vatRegistered:true,withholding:{code:"WC158"},origin:"foreign"}), {vat:"vat",withholding:"none:foreign"});
});
test("a supplier whose items differ in VAT leaves VAT to each line", () => {
  assert.deepEqual(billTaxDefaults({taxDefaultsConfirmed:true,vatRegistered:true,withholding:{code:"WC158"},origin:"local",vatVariesByItem:true}), {vat:"",withholding:"WC158"});
});
test("a saved line comes back as its code, its reason, or still to choose", () => {
  assert.equal(withholdingChoice({withholding:"WC160"}), "WC160");
  assert.equal(withholdingChoice({withholding:null,noWithholding:"not_covered"}), "none:not_covered");
  assert.equal(withholdingChoice({withholding:null}), "unconfirmed");
});
test("the choice goes to the API as a code or a reason with its note", () => {
  assert.deepEqual(withholdingPayload("WC158", "x"), {withholding:"WC158",noWithholdingReason:null,noWithholdingNote:null});
  assert.deepEqual(withholdingPayload("none:not_covered", "x"), {withholding:null,noWithholdingReason:"not_covered",noWithholdingNote:null});
  assert.deepEqual(withholdingPayload("none:other", " Rebate "), {withholding:null,noWithholdingReason:"other",noWithholdingNote:"Rebate"});
  assert.deepEqual(withholdingPayload("none:foreign", ""), {withholding:null,noWithholdingReason:null,noWithholdingNote:null});
});
