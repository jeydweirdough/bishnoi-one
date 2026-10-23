// TINs typed with the dashes put in for you (src/lib/tin.ts; asked 2026-10-22).

import assert from "node:assert/strict";
import test from "node:test";
import { formatTin } from "../src/lib/tin.ts";

test("digits get their dashes as they're typed", () => {
  assert.equal(formatTin("123"), "123");
  assert.equal(formatTin("1234"), "123-4");
  assert.equal(formatTin("123456789"), "123-456-789");
  assert.equal(formatTin("12345678900000"), "123-456-789-00000");
});

test("anything but digits is ignored, and dashes typed by hand don't double", () => {
  assert.equal(formatTin("123-456-789-000"), "123-456-789-000");
  assert.equal(formatTin("123 456 789"), "123-456-789");
  assert.equal(formatTin("12a3"), "123");
});

test("no more than a TIN's digits: 14 with a branch code, 9 for the company's own", () => {
  assert.equal(formatTin("1234567890000099"), "123-456-789-00000");
  assert.equal(formatTin("1234567890000", false), "123-456-789");
});

test("deleting a digit after a dash leaves no dash dangling", () => {
  assert.equal(formatTin("123-"), "123");
});
